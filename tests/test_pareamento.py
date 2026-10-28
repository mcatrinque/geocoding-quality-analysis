"""Testes do pareamento por identidade de endereço.

O protocolo de pareamento é a contribuição de maior alcance do trabalho, e o seu
comportamento em casos de borda precisa estar fixado: uma mudança silenciosa aqui
altera todos os números da dissertação.
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.metrics import (chave_identidade, conciliar_logradouros,
                         parear_por_identidade, separar_logradouro_numero)


@pytest.mark.parametrize('entrada, logradouro, numero', [
    ('RUA X, 100', 'RUA X', '100'),
    ('RUA W, 55 A', 'RUA W', '55 A'),
    ('AVENIDA SEM NUMERO', 'AVENIDA SEM NUMERO', None),
    # complemento depois do número: o corte recua para a vírgula anterior
    ('RUA Y, 10, SALA 2', 'RUA Y', '10'),
    ('RUA K, 7, APTO 301', 'RUA K', '7'),
])
def test_separar_logradouro_numero(entrada, logradouro, numero):
    log, num = separar_logradouro_numero(pd.Series([entrada]))
    assert log.iloc[0] == logradouro
    if numero is None:
        assert pd.isna(num.iloc[0])
    else:
        assert num.iloc[0] == numero


@pytest.mark.parametrize('numero, esperado', [
    ('0210', '210'), ('210', '210'), ('210 A', '210'), ('S/N', None), (None, None),
])
def test_chave_identidade_normaliza_numero(numero, esperado):
    _, num = chave_identidade(pd.Series(['av x']), pd.Series([numero]))
    if esperado is None:
        assert pd.isna(num.iloc[0])
    else:
        assert num.iloc[0] == esperado


REFERENCIA = ['RUA PIUM I', 'RUA PIUM II', 'AVENIDA TERESA CRISTINA', 'RUA OUTRA']


def test_conciliacao_aceita_variante_inequivoca():
    mapa = conciliar_logradouros(['AVENIDA TEREZA CRISTINA'], REFERENCIA, limiar=90, margem=2)
    assert mapa['AVENIDA TEREZA CRISTINA'] == 'AVENIDA TERESA CRISTINA'


def test_conciliacao_recusa_candidato_ambiguo():
    """A margem impede colar vias distintas de nomes quase idênticos."""
    mapa = conciliar_logradouros(['RUA PIUM'], REFERENCIA, limiar=90, margem=2)
    assert 'RUA PIUM' not in mapa


def test_conciliacao_recusa_sem_correspondente():
    mapa = conciliar_logradouros(['RUA COMPLETAMENTE DIFERENTE'], REFERENCIA, limiar=90, margem=2)
    assert mapa == {}


def test_pareamento_sem_nenhum_par_nao_quebra():
    alvo = gpd.GeoDataFrame(geometry=[Point(0, 0), Point(10, 10)], crs=31983)
    ref = gpd.GeoDataFrame(geometry=[Point(500, 500)], crs=31983)
    r = parear_por_identidade(
        alvo, ref,
        chave_identidade(pd.Series(['RUA A', 'RUA B']), pd.Series(['1', '2'])),
        chave_identidade(pd.Series(['RUA C']), pd.Series(['9'])))
    assert len(r) == 2
    assert not r['pareado_identidade'].any()
    assert r['dist_identidade'].isna().all()
    assert not r['chave_ambigua'].any()


def test_pareamento_usa_o_mais_proximo_da_mesma_chave():
    """Com vários pontos para o mesmo endereço, fica o mais próximo."""
    alvo = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=31983)
    ref = gpd.GeoDataFrame(geometry=[Point(300, 0), Point(20, 0)], crs=31983)
    r = parear_por_identidade(
        alvo, ref,
        chave_identidade(pd.Series(['RUA A']), pd.Series(['1'])),
        chave_identidade(pd.Series(['RUA A', 'RUA A']), pd.Series(['1', '1'])))
    assert r['dist_identidade'].iloc[0] == pytest.approx(20.0)
    # os candidatos distam 280 m entre si, acima do limite de ambiguidade
    assert bool(r['chave_ambigua'].iloc[0])
