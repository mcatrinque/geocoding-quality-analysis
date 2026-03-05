"""
Módulo de métricas de qualidade e completude.

Fornece funções para calcular completude de atributos, RMSE posicional
e resumos de qualidade da integração CNEFE/BHMap.
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List


def calculate_completeness(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """
    Calcula a porcentagem de valores preenchidos (não nulos e não vazios) por atributo.

    Args:
        df: DataFrame a ser analisado.
        columns: Lista de nomes de colunas para verificar.

    Returns:
        DataFrame com colunas 'Attribute', 'Valid Count', 'Missing Count' e 'Completeness (%)'.
    """
    stats = []
    total_rows = len(df)

    if total_rows == 0:
        return pd.DataFrame()

    for col in columns:
        if col not in df.columns:
            continue

        # Considera None, NaN, strings vazias e strings só com espaços como missing
        is_missing = df[col].isna() | (df[col].astype(str).str.strip() == '')

        valid_count = (~is_missing).sum()
        completeness_pct = (valid_count / total_rows) * 100

        stats.append({
            'Attribute': col,
            'Valid Count': valid_count,
            'Missing Count': is_missing.sum(),
            'Completeness (%)': round(completeness_pct, 2)
        })

    return pd.DataFrame(stats)


def calculate_positional_rmse(df: pd.DataFrame, error_col: str = 'spatial_distance') -> float:
    """
    Calcula o Root Mean Square Error (RMSE) da distância posicional em metros.

    Args:
        df: DataFrame contendo a coluna de erro.
        error_col: Nome da coluna com a distância de erro em metros.

    Returns:
        RMSE em metros, ou ``np.nan`` se não houver dados válidos.
    """
    if error_col not in df.columns or len(df) == 0:
        return np.nan

    valid_errors = df[error_col].dropna()
    if len(valid_errors) == 0:
        return np.nan

    rmse = np.sqrt(np.mean(valid_errors ** 2))
    return round(rmse, 2)


def generate_quality_summary(df: pd.DataFrame, mci_threshold: float = 0.8) -> Dict[str, Any]:
    """
    Gera um resumo conciso de qualidade focado nos matches de alta certeza.

    Args:
        df: DataFrame com colunas 'MCI' e 'spatial_distance'.
        mci_threshold: Limiar mínimo de MCI para considerar alta certeza.

    Returns:
        Dicionário com métricas agregadas de qualidade.
    """
    high_certainty = df[df['MCI'] >= mci_threshold]

    return {
        'total_records': len(df),
        'high_certainty_matches': len(high_certainty),
        'high_certainty_percent': round((len(high_certainty) / len(df)) * 100, 2) if len(df) > 0 else 0,
        'average_positional_error_m': round(high_certainty['spatial_distance'].mean(), 2) if 'spatial_distance' in high_certainty else np.nan,
        'positional_rmse_m': calculate_positional_rmse(high_certainty)
    }
