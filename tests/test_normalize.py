"""Testes da normalização de endereço.

A separação entre logradouro, número e pistas territoriais é o ponto em que a
consulta do usuário encontra a forma canônica do repositório. Quando ela falha,
a busca por similaridade casa com o logradouro errado e devolve uma coordenada
plausível para o endereço errado, que é o pior modo de falha possível num
geocodificador.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.normalize import normalize_logradouro, partes_endereco, split_logradouro_numero


@pytest.mark.parametrize('entrada, esperado', [
    ('av. afonso pena', 'AVENIDA AFONSO PENA'),
    ('R. dos Guajajaras', 'RUA DOS GUAJAJARAS'),
    ('Praça Sete de Setembro', 'PRACA SETE DE SETEMBRO'),
    ('  rua   da   bahia  ', 'RUA DA BAHIA'),
    ('Al. das Latânias', 'ALAMEDA DAS LATANIAS'),
])
def test_forma_canonica(entrada, esperado):
    assert normalize_logradouro(entrada) == esperado


@pytest.mark.parametrize('consulta, logradouro, numero, pistas', [
    ('Rua da Bahia, 1000, Centro, Belo Horizonte', 'RUA DA BAHIA', '1000',
     ['CENTRO', 'BELO HORIZONTE']),
    ('av. afonso pena 1212', 'AVENIDA AFONSO PENA', '1212', []),
    ('R. dos Guajajaras, 1000 - Centro', 'RUA DOS GUAJAJARAS', '1000', ['CENTRO']),
    ('rua sao paulo, n 100, centro', 'RUA SAO PAULO', '100', ['CENTRO']),
    ('Praça Sete de Setembro', 'PRACA SETE DE SETEMBRO', None, []),
])
def test_partes_endereco(consulta, logradouro, numero, pistas):
    assert partes_endereco(consulta) == (logradouro, numero, pistas)


def test_bairro_nao_contamina_o_logradouro():
    """Regressão: o bairro e a cidade não podem entrar no termo de busca.

    Com a versão anterior do parser, 'Rua da Bahia, 1000, Centro, Belo Horizonte'
    virava o termo 'RUA DA BAHIA 1000 CENTRO BELO HORIZONTE' e a busca por
    trigrama respondia 'RUA HORIZONTE'.
    """
    termo, _, _ = partes_endereco('Rua da Bahia, 1000, Centro, Belo Horizonte')
    assert termo == 'RUA DA BAHIA'
    assert 'HORIZONTE' not in termo


def test_compatibilidade_da_assinatura_antiga():
    assert split_logradouro_numero('av. afonso pena, 210') == ('AVENIDA AFONSO PENA', '210')


def test_entradas_degeneradas():
    assert partes_endereco(None) == ('', None, [])
    assert partes_endereco('   ') == ('', None, [])
    assert partes_endereco(',,,') == ('', None, [])


@pytest.mark.parametrize('texto,esperado', [
    ('Rua Teste, 010a, APTO 2', ('RUA TESTE', '10A', ['APTO 2'])),
    ('Rua Teste 010a', ('RUA TESTE', '10A', [])),
    ('Rua 7, 20', ('RUA 7', '20', [])),
])
def test_sufixo_e_numero_no_nome_da_via(texto, esperado):
    assert partes_endereco(texto) == esperado


@pytest.mark.parametrize('logradouro, tipo, nome', [
    ('AVENIDA AFONSO PENA', 'AVENIDA', 'AFONSO PENA'),
    ('RUA DOS GUAJAJARAS', 'RUA', 'DOS GUAJAJARAS'),
    ('PRACA SETE DE SETEMBRO', 'PRACA', 'SETE DE SETEMBRO'),
    ('SERRA VERDE', None, 'SERRA VERDE'),
])
def test_separar_tipo_logradouro(logradouro, tipo, nome):
    from src.normalize import separar_tipo_logradouro
    assert separar_tipo_logradouro(logradouro) == (tipo, nome)


@pytest.mark.parametrize('entrada, esperado', [
    ('30130-003', '30130003'),
    ('30130003', '30130003'),
    (' 30.130-003 ', '30130003'),
    ('3013000', None),
    ('00000000', None),
    (None, None),
    ('', None),
])
def test_normalize_cep(entrada, esperado):
    from src.normalize import normalize_cep
    assert normalize_cep(entrada) == esperado
