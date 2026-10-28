"""Casos sintéticos da carga, sem alterar o banco de trabalho."""

from contextlib import contextmanager
from types import SimpleNamespace

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from scripts import load_cnefe_to_postgis as carga


def _fonte_sintetica():
    return gpd.GeoDataFrame({
        'LOGRAD_NUM': ['RUA TESTE, 010, APTO 2', 'RUA TESTE, 10, APTO 3',
                       'RUA TESTE, 10A, LOJA 1'],
        'COMPLEMENTO': [None, None, None],
        'COD_UNICO_ENDERECO': ['7', '7', '8'],
        'CEP': ['30130000'] * 3,
    }, geometry=[Point(0, 0), Point(25, 0), Point(50, 0)], crs='EPSG:31983')


def test_parser_e_chave_de_numero_preservam_sufixo_e_complemento():
    args = SimpleNamespace(municipio='Belo Horizonte', uf='MG', codigo_ibge='3106200')
    rec = carga.preparar_registros(_fonte_sintetica(), args)
    assert rec['logradouro'].tolist() == ['RUA TESTE'] * 3
    assert rec['numero'].tolist() == ['10', '10', '10A']
    assert rec['numero_norm'].tolist() == [10, 10, 10]
    assert rec['complemento'].tolist() == ['APTO 2', 'APTO 3', 'LOJA 1']
    assert rec['origem_id'].tolist() == ['7', '7', '8']
    assert rec['origem_idx'].tolist() == [0, 1, 2]
    grupo, _, _ = carga.agrupar_por_endereco(rec, 30, 'EPSG:31983')
    assert grupo[0] == grupo[1]
    assert grupo[2] != grupo[0]


def test_chave_de_grupo_independe_da_ordem_das_linhas():
    rec = pd.DataFrame({'origem_idx': [9, 3]})
    grupo = pd.Series([0, 0])
    chave = carga.chaves_de_grupo(rec, grupo).iloc[0]
    rec_invertido = rec.iloc[::-1].reset_index(drop=True)
    assert carga.chaves_de_grupo(rec_invertido, grupo).iloc[0] == chave


def test_conectividade_nao_promete_diametro_de_trinta_metros():
    rec = gpd.GeoDataFrame({
        'codigo_municipio': ['3106200'] * 3,
        'logradouro': ['RUA TESTE'] * 3,
        'numero': ['10'] * 3,
    }, geometry=[Point(0, 0), Point(25, 0), Point(50, 0)], crs='EPSG:31983')
    grupo, x, y = carga.agrupar_por_endereco(rec, 30, 'EPSG:31983')
    assert len(set(grupo)) == 1
    endereco, _ = carga.consolidar(rec, grupo, x, y)
    assert endereco['dispersao_m'].iloc[0] == 50


def test_qualidade_opcional_nao_reduz_a_fonte(monkeypatch):
    fonte = _fonte_sintetica()
    qualidade = pd.DataFrame({
        'idx_cnefe_original': [1], 'LCI': [0.8], 'MCI': [0.5],
        'cdi': [2], 'GCI_empirico': [0.2],
    })
    monkeypatch.setattr(carga.pd, 'read_parquet', lambda *a, **k: qualidade)
    saida = carga.anexar_qualidade(fonte, 'qualidade.parquet')
    assert len(saida) == 3
    assert pd.isna(saida.loc[0, 'LCI'])
    assert saida.loc[1, 'LCI'] == 0.8
    assert pd.isna(saida.loc[2, 'LCI'])


class _Resultado:
    def __init__(self, valor):
        self.valor = valor

    def fetchone(self):
        return self.valor

    def scalars(self):
        return self

    def all(self):
        return self.valor

    def scalar(self):
        return self.valor


class _Conexao:
    def __init__(self):
        self.comandos = []

    def execute(self, sql, parametros=None):
        comando = str(sql)
        self.comandos.append((comando, parametros))
        if 'SELECT id_fonte' in comando:
            return _Resultado((5,))
        if "nextval('endereco_id_seq')" in comando:
            return _Resultado([1001])
        if "nextval('unidade_id_seq')" in comando:
            return _Resultado([2001])
        if 'SELECT count(*)' in comando:
            return _Resultado(1)
        return _Resultado(None)


class _Motor:
    def __init__(self):
        self.conexao = _Conexao()
        self.resultado = None

    @contextmanager
    def begin(self):
        try:
            yield self.conexao
        except Exception:
            self.resultado = 'rollback'
            raise
        else:
            self.resultado = 'commit'


def _quadros_promocao():
    endereco = gpd.GeoDataFrame({
        'grupo': [0], 'chave_carga': ['a' * 64], 'versao_fonte': ['2022'],
        'logradouro': ['RUA TESTE'], 'numero': ['10'], 'numero_norm': [10],
        'tipo_logradouro': ['RUA'], 'nome_logradouro': ['TESTE'],
        'bairro': [None], 'bairro_norm': [None], 'cep': [None],
        'municipio': ['Belo Horizonte'], 'uf': ['MG'], 'codigo_municipio': ['3106200'],
        'lci': [None], 'mci': [None], 'cdi': [None], 'gci': [None],
        'n_unidades': [1], 'n_coordenadas': [1], 'dispersao_m': [0],
        'latitude': [-19.9], 'longitude': [-43.9],
    }, geometry=[Point(-43.9, -19.9)], crs='EPSG:4326')
    unidade = pd.DataFrame({'grupo': [0], 'complemento': ['APTO 2']})
    origens = pd.DataFrame({'grupo': [0], 'codigo_municipio': ['3106200'],
                            'versao_fonte': ['2022'], 'origem_idx': [42],
                            'origem_id': ['7'], 'complemento': ['APTO 2'],
                            'lci': [None], 'mci': [None], 'cdi': [None], 'gci': [None]})
    return endereco, unidade, origens


MANIFESTO_TESTE = {
    'arquivo_sha256': '1' * 64, 'qualidade_sha256': None,
    'processamento_sha256': '2' * 64,
    'n_fonte': 1, 'n_validos': 1, 'n_enderecos': 1, 'n_complementos': 1,
}


@pytest.mark.parametrize('falhar', [False, True])
def test_promocao_restrita_e_atomica(monkeypatch, falhar):
    motor = _Motor()
    args = SimpleNamespace(fonte='CNEFE_2022', codigo_ibge='3106200', versao_fonte='2022')
    endereco, unidade, origens = _quadros_promocao()
    monkeypatch.setattr(carga.pd, 'read_sql', lambda *a, **k: pd.DataFrame(columns=['id_endereco', 'chave_carga', 'id_unidade', 'complemento']))
    def gravar_enderecos(self, name, con, **kwargs):
        assert con is motor.conexao
        assert self['id_endereco'].tolist() == [1001]
        if falhar:
            raise RuntimeError('falha de escrita simulada')
    monkeypatch.setattr(gpd.GeoDataFrame, 'to_postgis', gravar_enderecos)
    gravacoes = []
    monkeypatch.setattr(pd.DataFrame, 'to_sql',
                        lambda self, name, con, **kwargs: gravacoes.append((name, con, self.copy())))

    if falhar:
        with pytest.raises(RuntimeError, match='simulada'):
            carga.promover_carga(motor, args, endereco, unidade, origens, MANIFESTO_TESTE)
        assert motor.resultado == 'rollback'
        assert not gravacoes
    else:
        assert carga.promover_carga(motor, args, endereco, unidade, origens,
                                   MANIFESTO_TESTE) == 1
        assert motor.resultado == 'commit'
        assert [g[0] for g in gravacoes] == ['unidade', 'registro_origem']
        assert all(g[1] is motor.conexao for g in gravacoes)
        assert gravacoes[1][2]['origem_idx'].tolist() == [42]
    exclusoes = [(q, p) for q, p in motor.conexao.comandos if q.startswith('DELETE')]
    assert len(exclusoes) == 3
    assert all('id_fonte = :f' in q and 'codigo_municipio = :m' in q
               and 'versao_fonte = :v' in q for q, _ in exclusoes)
    assert all(p == {'f': 5, 'm': '3106200', 'v': '2022'} for _, p in exclusoes)


def test_recarga_reutiliza_id_da_mesma_chave(monkeypatch):
    motor = _Motor()
    args = SimpleNamespace(fonte='CNEFE_2022', codigo_ibge='3106200', versao_fonte='2022')
    endereco, unidade, origens = _quadros_promocao()
    monkeypatch.setattr(carga.pd, 'read_sql', lambda sql, *a, **k:
        pd.DataFrame(columns=['id_unidade','id_endereco','complemento'])
        if 'FROM unidade u' in str(sql) else pd.DataFrame({
            'id_endereco': [89], 'chave_carga': ['a' * 64]}))
    ids_gravados = []
    monkeypatch.setattr(gpd.GeoDataFrame, 'to_postgis',
                        lambda self, *a, **k: ids_gravados.extend(self['id_endereco'].tolist()))
    monkeypatch.setattr(pd.DataFrame, 'to_sql', lambda *a, **k: None)
    carga.promover_carga(motor, args, endereco, unidade, origens, MANIFESTO_TESTE)
    assert ids_gravados == [89]
    assert not any("nextval('endereco_id_seq')" in sql for sql, _ in motor.conexao.comandos)


def test_hash_processamento_muda_com_parametros():
    args = SimpleNamespace(raio_fusao=30.0, crs_metrico='EPSG:31983')
    original = carga.hash_processamento(args)
    args.raio_fusao = 25.0
    assert carga.hash_processamento(args) != original
    args.raio_fusao = 30.0
    args.crs_metrico = 'EPSG:31982'
    assert carga.hash_processamento(args) != original


def test_promocao_sem_manifesto_nao_inicia_transacao():
    motor = _Motor()
    args = SimpleNamespace(fonte='CNEFE_2022', codigo_ibge='3106200', versao_fonte='2022')
    endereco, unidade, origens = _quadros_promocao()
    with pytest.raises(ValueError, match='Manifesto obrigatório'):
        carga.promover_carga(motor, args, endereco, unidade, origens)
    assert motor.conexao.comandos == []
