"""Invariantes da associação de métricas à origem CNEFE."""

import pandas as pd
import pytest

from src.linhagem import juntar_por_origem


def _dados():
    base = pd.DataFrame(
        {"idx_cnefe_original": [30, 10, 20], "endereco": ["C", "A", "B"]},
        index=pd.Index([8, 8, 2], name="indice_pareamento"),
    )
    atributos = pd.DataFrame(
        {"CDI": [1, 2, 3, 9], "CCR": [True, False, True, False]},
        index=pd.Index([10, 20, 30, 40], name="idx_cnefe_original"),
    )
    return base, atributos


def test_juncao_independe_da_ordem_e_preserva_indice_e_cardinalidade():
    base, atributos = _dados()
    esperado = [3, 1, 2]
    for ordem_base in ([0, 1, 2], [2, 0, 1]):
        for ordem_atributos in ([0, 1, 2, 3], [3, 2, 1, 0]):
            atual = base.iloc[ordem_base]
            obtido = juntar_por_origem(atual, atributos.iloc[ordem_atributos])
            assert len(obtido) == len(atual)
            assert obtido.index.equals(atual.index)
            assert obtido["idx_cnefe_original"].tolist() == atual["idx_cnefe_original"].tolist()
            assert obtido["CDI"].tolist() == [esperado[i] for i in ordem_base]
            assert obtido["endereco"].tolist() == atual["endereco"].tolist()


def test_selecao_de_colunas_e_chave_explicita_a_direita():
    base, atributos = _dados()
    direita = atributos.reset_index()
    obtido = juntar_por_origem(base, direita, colunas=["CDI"])
    assert obtido.columns.tolist() == ["idx_cnefe_original", "endereco", "CDI"]
    assert obtido["CDI"].tolist() == [3, 1, 2]


@pytest.mark.parametrize(
    "alterar, mensagem",
    [
        (lambda b, a: (b.drop(columns="idx_cnefe_original"), a), "não contém a chave"),
        (lambda b, a: (b.assign(idx_cnefe_original=[30, None, 20]), a), "nulas"),
        (lambda b, a: (b.assign(idx_cnefe_original=[30, 30, 20]), a), "duplicadas"),
        (lambda b, a: (b, a.set_axis([10, None, 30, 40])), "nulas"),
        (lambda b, a: (b, a.set_axis([10, 10, 30, 40])), "duplicadas"),
        (lambda b, a: (b, a.drop(index=30)), "Faltam atributos"),
        (lambda b, a: (b.assign(CDI=0), a), "já presentes"),
    ],
)
def test_juncao_recusa_linhagem_ambigua_ou_incompleta(alterar, mensagem):
    base, atributos = _dados()
    base, atributos = alterar(base, atributos)
    with pytest.raises(ValueError, match=mensagem):
        juntar_por_origem(base, atributos)


def test_juncao_recusa_coluna_pedida_ausente():
    base, atributos = _dados()
    with pytest.raises(ValueError, match="Colunas ausentes"):
        juntar_por_origem(base, atributos, colunas=["DRS"])
