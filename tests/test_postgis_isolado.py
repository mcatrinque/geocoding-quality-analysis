"""Integração destrutiva restrita ao banco sintético dedicado da auditoria."""

import hashlib
import os
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts import load_cnefe_to_postgis as carga


@pytest.fixture(scope='module')
def repositorio(tmp_path_factory):
    url = os.environ.get('GEOCODING_TEST_DATABASE_URL')
    if not url:
        pytest.skip('GEOCODING_TEST_DATABASE_URL não definida para banco isolado')
    destino = make_url(url)
    if (destino.host not in {'127.0.0.1', 'localhost'} or destino.port != 55439
            or destino.database != 'geocoding_auditoria_20260930'):
        pytest.fail('Integração permitida somente no banco sintético dedicado')
    engine = create_engine(url)
    pasta = tmp_path_factory.mktemp('fontes_sinteticas')
    bh = gpd.GeoDataFrame({
        'LOGRAD_NUM': ['AVENIDA AFONSO PENA, 1212', 'AVENIDA AFONSO PENA, 1212',
                       'AVENIDA AFONSO PENA, 1212A', 'RUA DA BAHIA, 1000'],
        'COMPLEMENTO': ['APTO 1', 'APTO 2', 'LOJA A', None],
        'COD_UNICO_ENDERECO': ['1', '2', '3', '4'],
        'CEP': ['30130000'] * 4,
        'cdi': [2.0, 2.0, float('nan'), 1.0],
    }, geometry=[Point(-43.9386, -19.9191), Point(-43.9386, -19.9191),
                 Point(-43.9385, -19.9191), Point(-43.9400, -19.9200)], crs=4326)
    outra = gpd.GeoDataFrame({
        'LOGRAD_NUM': ['AVENIDA AFONSO PENA, 1212'],
        'COMPLEMENTO': [None], 'COD_UNICO_ENDERECO': ['1'], 'CEP': ['32000000'],
    }, geometry=[Point(-44.0500, -19.9200)], crs=4326)
    bh.to_parquet(pasta/'bh.parquet')
    outra.to_parquet(pasta/'contagem.parquet')

    def carregar(arquivo, codigo='3106200', municipio='Belo Horizonte'):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv('DATABASE_URL', url)
            mp.setattr(sys, 'argv', ['carga', '--parquet', str(arquivo),
                                    '--codigo-ibge', codigo, '--municipio', municipio,
                                    '--fonte', 'AUDITORIA_SINTETICA', '--versao-fonte', 'v1'])
            carga.carregar()

    carregar(pasta/'bh.parquet')
    carregar(pasta/'contagem.parquet', '3118601', 'Contagem')
    yield engine, pasta, carregar
    engine.dispose()


def _estado(engine):
    with engine.connect() as conn:
        return {
            tabela: conn.execute(text(f'SELECT * FROM {tabela} ORDER BY 1,2,3')).all()
            for tabela in ['endereco', 'unidade', 'registro_origem', 'carga_repositorio',
                           'logradouro_busca']
        }


def test_recarga_preserva_ids_origens_e_outro_municipio(repositorio):
    engine, pasta, carregar = repositorio
    antes = _estado(engine)
    carregar(pasta/'bh.parquet')
    depois = _estado(engine)
    for tabela in ['endereco', 'unidade', 'registro_origem', 'logradouro_busca']:
        assert antes[tabela] == depois[tabela]
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM endereco')).scalar_one() == 4
        assert conn.execute(text('SELECT count(*) FROM registro_origem')).scalar_one() == 5
        assert conn.execute(text('SELECT count(*) FROM carga_repositorio')).scalar_one() == 2
        assert conn.execute(text('SELECT count(*) FROM endereco WHERE cdi IS NULL')).scalar_one() == 2
        assert conn.execute(text('SELECT count(*) FROM registro_origem WHERE cdi = 2')).scalar_one() == 2


def test_falha_apos_inserir_enderecos_reverte_toda_carga(repositorio, monkeypatch):
    engine, pasta, carregar = repositorio
    antes = _estado(engine)
    original = carga.pd.DataFrame.to_sql

    def falhar(df, name, *args, **kwargs):
        if name == 'unidade':
            raise RuntimeError('Falha injetada após escrever endereços')
        return original(df, name, *args, **kwargs)

    monkeypatch.setattr(carga.pd.DataFrame, 'to_sql', falhar)
    with pytest.raises(RuntimeError, match='Falha injetada'):
        carregar(pasta/'bh.parquet')
    assert antes == _estado(engine)


@pytest.fixture(scope='module')
def cliente_isolado(repositorio):
    from src.api import main
    from fastapi.testclient import TestClient
    destino = make_url(main.engine.url)
    assert destino.database == 'geocoding_auditoria_20260930' and destino.port == 55439
    with TestClient(main.app) as cliente:
        yield cliente


def test_homonimos_nao_cruzam_municipios_e_sufixo_e_preservado(cliente_isolado):
    for codigo, longitude in [('3106200', -43.9386), ('3118601', -44.05)]:
        resposta = cliente_isolado.post('/geocode', json={
            'endereco': 'Avenida Afonso Pena, 1212', 'codigo_municipio': codigo})
        assert resposta.status_code == 200, resposta.text
        candidatos = resposta.json()['candidatos']
        assert candidatos and all(c['codigo_municipio'] == codigo for c in candidatos)
        assert candidatos[0]['longitude'] == pytest.approx(longitude, abs=1e-7)
        assert candidatos[0]['versao_dados'] and len(candidatos[0]['versao_dados']) == 64
        assert candidatos[0]['qualidade']['calibracao']['status'] == 'declarada'
    resposta = cliente_isolado.post('/geocode', json={
        'endereco': 'Avenida Afonso Pena, 1212A', 'codigo_municipio': '3106200'})
    assert resposta.json()['candidatos'][0]['numero'] == '1212A'


def test_reverse_proximidade_metros_sem_calibracao_textual(cliente_isolado):
    resposta = cliente_isolado.post('/reverse', json={
        'latitude': -19.9191, 'longitude': -43.93859, 'raio_m': 100})
    assert resposta.status_code == 200, resposta.text
    candidato = resposta.json()
    assert candidato['numero'] == '1212'
    assert .5 < candidato['distancia_m'] < 2
    assert candidato['nivel_precisao'] == 'proximidade'
    assert candidato['qualidade']['calibracao']['status'] == 'declarada'
