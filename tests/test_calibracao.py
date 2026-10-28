"""Testes da declaração de calibração da API.

O que se verifica aqui não é aritmética, e sim uma regra de honestidade: o
serviço só afirma erro em metros onde houve verdade de campo, recua de
granularidade quando a célula é fina demais para sustentar quantil, e prefere
não informar a informar sem lastro.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.calibracao import Calibrador, carregar
from src.api.schemas import ClasseConfianca, NivelPrecisao, StatusCalibracao

BH = '3106200'
RAIZ = Path(__file__).resolve().parents[1]
VERSAO_TESTE = 'a' * 64

LINHAS = [
    {'codigo_municipio': BH, 'nivel': 'numero_exato', 'confianca': 'alta',
     'base': 'nivel+confianca', 'n': '16217', 'erro_mediano_m': '8.2',
     'erro_ce90_m': '20.98', 'acima_30_pct': '5.77', 'acima_100_pct': '1.83'},
    {'codigo_municipio': BH, 'nivel': 'numero_exato', 'confianca': '',
     'base': 'nivel', 'n': '16391', 'erro_mediano_m': '8.23',
     'erro_ce90_m': '21.1', 'acima_30_pct': '5.8', 'acima_100_pct': '1.81'},
    {'codigo_municipio': BH, 'nivel': '', 'confianca': '',
     'base': 'global', 'n': '19924', 'erro_mediano_m': '9.38',
     'erro_ce90_m': '57.94', 'acima_30_pct': '14.76', 'acima_100_pct': '7.99'},
]
for linha in LINHAS:
    linha.update(versao_dados=VERSAO_TESTE, versao_politica='politica-teste',
                 tipo_consulta='geocode', amostra='teste_independente',
                 fonte_referencia='BHMap')


def consultar(calibrador, municipio, nivel, confianca):
    return calibrador.consultar(municipio, nivel, confianca,
                                versao_dados=VERSAO_TESTE,
                                versao_politica='politica-teste')


@pytest.fixture
def calibrador():
    return Calibrador(LINHAS)


def test_celula_exata_usa_a_granularidade_mais_fina(calibrador):
    c = consultar(calibrador, BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA)
    assert c.status is StatusCalibracao.CALIBRADA
    assert c.base == 'nivel+confianca'
    assert c.erro_mediano_m == 8.2
    assert c.erro_ce90_m == 20.98
    assert c.n_amostra == 16217


def test_par_ausente_recua_para_o_nivel(calibrador):
    """A combinação exato+baixa não foi medida; a resposta recua, e diz que recuou."""
    c = consultar(calibrador, BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.BAIXA)
    assert c.status is StatusCalibracao.CALIBRADA
    assert c.base == 'nivel'
    assert c.erro_mediano_m == 8.23


def test_nivel_ausente_recua_para_o_global(calibrador):
    c = consultar(calibrador, BH, NivelPrecisao.LOGRADOURO, ClasseConfianca.BAIXA)
    assert c.base == 'global'
    assert c.erro_mediano_m == 9.38


def test_municipio_sem_verdade_de_campo_nao_afirma_erro(calibrador):
    """O ponto central: responder para todo o Brasil não é o mesmo que garantir qualidade."""
    c = consultar(calibrador, '3550308', NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA)
    assert c.status is StatusCalibracao.DECLARADA
    assert c.erro_mediano_m is None
    assert c.erro_ce90_m is None
    assert c.n_amostra is None


def test_municipio_nulo_nao_afirma_erro(calibrador):
    assert consultar(calibrador, None, NivelPrecisao.NUMERO_EXATO,
                     ClasseConfianca.ALTA).status is StatusCalibracao.DECLARADA


def test_referencia_nomeia_a_fonte_da_verdade(calibrador):
    c = consultar(calibrador, BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA)
    assert 'BHMap' in c.referencia
    assert '19.924' in c.referencia


def test_tabela_ausente_nao_derruba_o_servico(tmp_path):
    """Sem tabela, tudo sai como declarado. Falhar seria pior que não afirmar."""
    vazio = carregar(tmp_path / 'inexistente.csv')
    assert vazio.municipios_calibrados == []
    assert vazio.consultar(BH, NivelPrecisao.NUMERO_EXATO,
                           ClasseConfianca.ALTA).status is StatusCalibracao.DECLARADA


def test_tabela_corrompida_nao_derruba_o_servico(tmp_path):
    ruim = tmp_path / 'ruim.csv'
    ruim.write_bytes(b'\xff\xfe isto nao e csv valido \x00')
    assert carregar(ruim).consultar(BH, NivelPrecisao.NUMERO_EXATO,
                                    ClasseConfianca.ALTA).status is StatusCalibracao.DECLARADA


def test_tabela_de_desenvolvimento_continua_inelegivel():
    """A tabela histórica, estimada na amostra de ajuste, não pode virar teste independente."""
    historica = carregar(RAIZ / 'dados_replicacao' / 'calibracao_bh_desenvolvimento_20260911.csv')
    assert BH not in historica.municipios_calibrados


def test_tabela_instalada_so_calibra_a_versao_testada():
    """A tabela do teste independente (NB17) vale só para os dados e a política em que foi medida."""
    real = carregar()
    assert real.municipios_calibrados == [BH]
    with (RAIZ / 'dados_replicacao' / 'calibracao_bh.csv').open(encoding='utf-8') as f:
        linha = next(csv.DictReader(f))
    assert linha['amostra'] == 'teste_independente'
    versoes = dict(versao_dados=linha['versao_dados'], versao_politica=linha['versao_politica'])
    c = real.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA, **versoes)
    assert c.status is StatusCalibracao.CALIBRADA and c.erro_ce90_m is not None
    for nivel in NivelPrecisao:
        for classe in ClasseConfianca:
            assert real.consultar(BH, nivel, classe).status is StatusCalibracao.DECLARADA
            outra = real.consultar(BH, nivel, classe, versao_dados='0' * 64,
                                   versao_politica=linha['versao_politica'])
            assert outra.status is StatusCalibracao.DECLARADA


# ── Efeito sobre a resposta montada ────────────────────────────────────────────


@dataclass
class LinhaFalsa:
    codigo_municipio: Optional[str] = BH
    gci: Optional[float] = 0.9
    lci: Optional[float] = 1.0
    mci: Optional[float] = 0.9
    cdi: Optional[int] = 1
    dispersao_m: Optional[float] = 0.0
    n_unidades: Optional[int] = 1


def carregar_avaliador():
    try:
        from src.api.main import avaliar_qualidade
    except Exception as erro:  # pragma: no cover - ambiente sem dependências da API
        pytest.skip(f'API indisponível: {erro}')
    return avaliar_qualidade


def test_resposta_em_bh_nao_traz_estimativa_sem_teste_independente():
    avaliar = carregar_avaliador()
    q = avaliar(LinhaFalsa(), NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert q.calibracao.status is StatusCalibracao.DECLARADA
    assert q.gci_empirico is None
    assert 'teste independente' in q.motivo


def test_resposta_fora_de_bh_omite_o_indice_composto():
    """O PCI do índice foi calibrado em BH; fora dali o número não tem lastro."""
    avaliar = carregar_avaliador()
    q = avaliar(LinhaFalsa(codigo_municipio='3550308'), NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert q.calibracao.status is StatusCalibracao.DECLARADA
    assert q.gci_empirico is None
    assert 'não foi verificada aqui' in q.motivo


def test_classes_continuam_validas_fora_de_bh():
    """Só o erro em metros depende de verdade de campo; o casamento é observável em qualquer lugar."""
    avaliar = carregar_avaliador()
    q = avaliar(LinhaFalsa(codigo_municipio='3550308'), NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert q.confianca_posicional is ClasseConfianca.ALTA
    assert q.incerteza_identidade is not None
