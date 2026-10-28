"""Testes da API do repositório de endereços.

Os testes de classificação de confiança rodam sem banco. Os de contrato exigem
o PostGIS carregado e são pulados quando ele não está disponível, para que a
suíte continue útil em ambiente sem Docker.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass
class LinhaFalsa:
    """Substituto de uma linha do banco, para testar a regra de confiança."""
    gci: Optional[float] = 0.9
    lci: Optional[float] = 1.0
    mci: Optional[float] = 0.9
    cdi: Optional[int] = 1
    dispersao_m: Optional[float] = 0.0
    n_unidades: Optional[int] = 1


def carregar_api():
    try:
        from src.api import main
        return main
    except Exception as erro:                                 # pragma: no cover
        pytest.skip(f'API indisponível neste ambiente: {erro}')


def test_dimensoes_de_qualidade_sao_separadas():
    """Regressão: uma etiqueta única misturava posição e identidade.

    Medido em 20.000 endereços, o índice composto separava erro posicional acima
    de 30 m com AUC de 0,58. As duas dimensões passam a ser reportadas à parte.
    """
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    predio = main.avaliar_qualidade(LinhaFalsa(gci=0.01, cdi=200),
                                    NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert predio.confianca_posicional is ClasseConfianca.ALTA
    assert predio.incerteza_identidade is ClasseConfianca.ALTA


def test_confianca_alta_exige_casamento_exato():
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    boa = main.avaliar_qualidade(LinhaFalsa(), NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert boa.confianca_posicional is ClasseConfianca.ALTA


def test_numero_inexistente_nao_pode_ser_alta_confianca():
    """Regressão: 'Avenida Afonso Pena, 999999' devolvia confiança alta.

    A classe descrevia o ponto guardado, não a resposta à consulta. Um número
    que não existe no repositório é, no máximo, confiança moderada.
    """
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    q = main.avaliar_qualidade(LinhaFalsa(gci=0.95), NivelPrecisao.NUMERO_APROXIMADO, 1.0, 5)
    assert q.confianca_posicional is ClasseConfianca.MODERADA
    assert 'não existe' in q.motivo


def test_logradouro_sem_numero_e_confianca_baixa():
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    q = main.avaliar_qualidade(LinhaFalsa(gci=0.99), NivelPrecisao.LOGRADOURO, 1.0, None)
    assert q.confianca_posicional is ClasseConfianca.BAIXA


def test_similaridade_ruim_rebaixa_a_confianca():
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    q = main.avaliar_qualidade(LinhaFalsa(gci=0.95), NivelPrecisao.NUMERO_EXATO, 0.40, 0)
    assert q.confianca_posicional is ClasseConfianca.BAIXA


def test_dispersao_alta_rebaixa_a_confianca():
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    q = main.avaliar_qualidade(LinhaFalsa(gci=0.95, dispersao_m=120.0),
                               NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert q.confianca_posicional is ClasseConfianca.MODERADA
    assert 'discordam' in q.motivo


def test_coordenada_compartilhada_e_declarada():
    main = carregar_api()
    from src.api.schemas import ClasseConfianca, NivelPrecisao

    q = main.avaliar_qualidade(LinhaFalsa(gci=0.2, cdi=88), NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert 'compartilham' in q.motivo
    assert q.cdi == 88
    assert q.incerteza_identidade is ClasseConfianca.ALTA


# ---------------------------------------------------------------------------
# Contrato, com banco carregado
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def cliente():
    main = carregar_api()
    try:
        from fastapi.testclient import TestClient
    except ImportError:                                        # pragma: no cover
        pytest.skip('httpx/TestClient não instalado')
    with TestClient(main.app) as c:
        try:
            saude = c.get('/health')
        except Exception as erro:
            pytest.skip(f'banco indisponível: {erro}')
        if saude.status_code != 200 or saude.json()['enderecos'] == 0:
            pytest.skip('repositório vazio ou banco indisponível')
        yield c


def test_health(cliente):
    corpo = cliente.get('/health').json()
    assert corpo['status'] == 'ok'
    assert corpo['enderecos'] > 0


def test_cobertura_declara_o_territorio(cliente):
    corpo = cliente.get('/cobertura').json()
    assert corpo, 'a rota de cobertura precisa dizer o que está carregado'
    assert {'municipio', 'uf', 'enderecos', 'fonte'} <= set(corpo[0])


def test_geocode_numero_exato(cliente):
    corpo = cliente.post('/geocode', json={'endereco': 'Avenida Afonso Pena, 1212'}).json()
    primeiro = corpo['candidatos'][0]
    assert primeiro['logradouro'] == 'AVENIDA AFONSO PENA'
    assert primeiro['numero'] == '1212'
    assert primeiro['nivel_precisao'] == 'numero_exato'
    assert primeiro['plus_code']


def test_geocode_tolera_abreviacao(cliente):
    corpo = cliente.post('/geocode', json={'endereco': 'av. afonso pena 1212'}).json()
    assert corpo['candidatos'][0]['numero'] == '1212'


def test_geocode_com_bairro_e_cidade_no_texto(cliente):
    """Regressão: a consulta completa devolvia outro logradouro com confiança alta."""
    corpo = cliente.post('/geocode', json={
        'endereco': 'Rua da Bahia, 1000, Centro, Belo Horizonte'}).json()
    assert corpo['logradouro_normalizado'] == 'RUA DA BAHIA'
    assert corpo['candidatos'][0]['logradouro'] == 'RUA DA BAHIA'


def test_numero_muito_distante_degrada_para_logradouro(cliente):
    """Numeração fora de alcance não sustenta resposta no nível do imóvel.

    Calibrado no NB14: acima de 20 de diferença na numeração, a mediana do erro
    sobe de cerca de 25 m para mais de 60 m, e acima de 100 chega a 220 m. A
    resposta passa a valer como referência de logradouro.
    """
    corpo = cliente.post('/geocode', json={'endereco': 'Avenida Afonso Pena, 999999'}).json()
    primeiro = corpo['candidatos'][0]
    assert primeiro['nivel_precisao'] == 'logradouro'
    assert primeiro['qualidade']['confianca_posicional'] == 'baixa'


def test_numero_proximo_e_declarado_como_aproximado(cliente):
    """Diferença pequena de numeração continua valendo como resposta de imóvel."""
    corpo = cliente.post('/geocode', json={'endereco': 'Avenida Afonso Pena, 1213'}).json()
    primeiro = corpo['candidatos'][0]
    assert primeiro['nivel_precisao'] in ('numero_exato', 'numero_aproximado')
    if primeiro['nivel_precisao'] == 'numero_aproximado':
        assert primeiro['diferenca_numero'] <= main_diferenca_maxima()
        assert primeiro['qualidade']['confianca_posicional'] in ('moderada', 'baixa')


def main_diferenca_maxima():
    from src.api import main
    return main.DIFERENCA_NUMERO_MAXIMA


def test_logradouro_mal_casado_e_recusado(cliente):
    """Abaixo do piso de similaridade, o serviço recusa em vez de responder longe.

    Na amostra do NB14, as consultas com similaridade abaixo de 0,9 eram 4,4% do
    total e concentravam 29% dos erros acima de 100 m, com mediana de 9,3 km nos
    casamentos mais fracos.
    """
    resposta = cliente.post('/geocode', json={'endereco': 'Rua Xyzabcdef Inexistente, 1'})
    assert resposta.status_code == 404
    detalhe = resposta.json()['detail']
    assert 'similaridade' in detalhe or 'Nenhum endereço compatível' in detalhe


def test_geocode_sem_resultado_responde_404(cliente):
    resposta = cliente.post('/geocode', json={'endereco': 'Rua Que Nao Existe Xyzabcdef, 1'})
    assert resposta.status_code == 404


def test_geocode_respeita_o_recorte_de_municipio(cliente):
    resposta = cliente.post('/geocode', json={
        'endereco': 'Avenida Afonso Pena, 1212', 'municipio': 'Curitiba'})
    assert resposta.status_code == 404


def test_reverse_devolve_distancia(cliente):
    corpo = cliente.post('/reverse', json={
        'latitude': -19.9191, 'longitude': -43.9386}).json()
    assert corpo['distancia_m'] >= 0
    assert corpo['qualidade']['confianca_posicional'] in ('alta', 'moderada', 'baixa')


def test_reverse_fora_do_raio_responde_404(cliente):
    resposta = cliente.post('/reverse', json={
        'latitude': 0.0, 'longitude': 0.0, 'raio_m': 100})
    assert resposta.status_code == 404


def test_usage_contabiliza_no_banco(cliente):
    corpo = cliente.get('/usage').json()
    assert corpo['total'] >= 0
    assert isinstance(corpo['por_rota'], list)
