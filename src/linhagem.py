"""Junções de atributos calculados no registro original do CNEFE."""

from collections.abc import Sequence

import pandas as pd


def juntar_por_origem(
    base: pd.DataFrame,
    atributos: pd.DataFrame,
    colunas: Sequence[str] | None = None,
    chave: str = "idx_cnefe_original",
) -> pd.DataFrame:
    """Anexa atributos por identificador de origem e preserva a base integralmente.

    ``base[chave]`` identifica cada registro uma única vez. No lado direito, a
    chave pode ser o índice (caso das métricas do NB03) ou uma coluna explícita.
    Chaves adicionais no lado direito são permitidas, pois a base pode ser um
    subconjunto dos registros originais. Toda chave da base deve estar presente.
    """
    if not isinstance(base, pd.DataFrame) or not isinstance(atributos, pd.DataFrame):
        raise TypeError("base e atributos devem ser DataFrames")
    if not base.columns.is_unique or not atributos.columns.is_unique:
        raise ValueError("Os nomes das colunas devem ser únicos em ambos os lados")
    if chave not in base.columns:
        raise ValueError(f"A base não contém a chave de origem '{chave}'")
    if base[chave].isna().any():
        raise ValueError(f"A base contém chaves de origem nulas em '{chave}'")
    if base[chave].duplicated().any():
        raise ValueError(f"A base contém chaves de origem duplicadas em '{chave}'")

    direita = atributos.set_index(chave, drop=True) if chave in atributos.columns else atributos
    if direita.index.hasnans:
        raise ValueError(f"Os atributos contêm chaves de origem nulas em '{chave}'")
    if not direita.index.is_unique:
        raise ValueError(f"Os atributos contêm chaves de origem duplicadas em '{chave}'")

    selecionadas = list(direita.columns) if colunas is None else list(colunas)
    if not selecionadas:
        raise ValueError("Selecione ao menos uma coluna de atributos")
    if len(selecionadas) != len(set(selecionadas)):
        raise ValueError("A seleção contém colunas de atributos repetidas")
    ausentes = [col for col in selecionadas if col not in direita.columns]
    if ausentes:
        raise ValueError(f"Colunas ausentes nos atributos: {ausentes}")
    sobrepostas = [col for col in selecionadas if col in base.columns]
    if sobrepostas:
        raise ValueError(f"Colunas já presentes na base: {sobrepostas}")

    posicoes = direita.index.get_indexer(base[chave])
    faltam = posicoes == -1
    if faltam.any():
        exemplos = base.loc[faltam, chave].head(5).tolist()
        raise ValueError(
            f"Faltam atributos para {int(faltam.sum())} chaves de origem "
            f"da base em '{chave}'. Exemplos: {exemplos}"
        )

    resultado = base.copy()
    alinhados = direita[selecionadas].iloc[posicoes]
    for coluna in selecionadas:
        resultado[coluna] = alinhados[coluna].array
    if len(resultado) != len(base) or not resultado.index.equals(base.index):
        raise AssertionError("A junção alterou a cardinalidade ou o índice da base")
    return resultado
