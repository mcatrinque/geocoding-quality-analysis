"""
segments.py — Funções de Segmentação e Análise Comparativa por Categoria
"""
import pandas as pd
import numpy as np
from scipy import stats


def classify_especie(df, col='COD_ESPECIE', map_dict=None):
    """Adiciona coluna 'especie_label' com rótulo legível da espécie."""
    if map_dict is None:
        from src.config import ESPECIE_MAP
        map_dict = ESPECIE_MAP
    df = df.copy()
    df['especie_label'] = df[col].map(map_dict).fillna('Desconhecido')
    return df


def classify_tipo_residencial(df, col='COD_TIPO_ESPECI', map_dict=None):
    """Adiciona coluna 'tipo_resid_label' com rótulo legível do sub-tipo."""
    if map_dict is None:
        from src.config import TIPO_ESPECIE_MAP
        map_dict = TIPO_ESPECIE_MAP
    df = df.copy()
    df['tipo_resid_label'] = df[col].map(map_dict).fillna('N/A')
    return df


def classify_nv_geo(df, col='NV_GEO_COORD', map_dict=None):
    """Adiciona coluna 'nv_geo_label' com rótulo do nível de geocodificação."""
    if map_dict is None:
        from src.config import NV_GEO_MAP
        map_dict = NV_GEO_MAP
    df = df.copy()
    df['nv_geo_label'] = df[col].map(map_dict).fillna('Desconhecido')
    return df


def add_all_labels(df):
    """Aplica todas as classificações de uma vez."""
    df = classify_especie(df)
    df = classify_tipo_residencial(df)
    df = classify_nv_geo(df)
    return df


def metrics_by_segment(df, segment_col, distance_col='match_distance'):
    """
    Calcula métricas de qualidade agrupadas por segmento.

    Returns:
        DataFrame com colunas: n, LCI_mean, MCI_mean, PCI_mean, GCI_mean,
        GCI_median, GCI_std, RMSE, CE90, MAE, match_rate
    """
    from src.metrics import calculate_rmse, calculate_ce90, calculate_mae

    results = []
    for name, group in df.groupby(segment_col, observed=True):
        dist = group[distance_col].dropna()
        row = {
            'segmento': name,
            'n': len(group),
            'pct': len(group) / len(df) * 100,
            'LCI_mean': group['LCI'].mean() if 'LCI' in group else np.nan,
            'MCI_mean': group['MCI'].mean() if 'MCI' in group else np.nan,
            'PCI_mean': group['PCI'].mean() if 'PCI' in group else np.nan,
            'GCI_mean': group['GCI'].mean() if 'GCI' in group else np.nan,
            'GCI_median': group['GCI'].median() if 'GCI' in group else np.nan,
            'GCI_std': group['GCI'].std() if 'GCI' in group else np.nan,
            'RMSE': calculate_rmse(dist) if len(dist) > 0 else np.nan,
            'CE90': calculate_ce90(dist) if len(dist) > 0 else np.nan,
            'MAE': calculate_mae(dist) if len(dist) > 0 else np.nan,
        }
        results.append(row)

    return pd.DataFrame(results).sort_values('n', ascending=False).reset_index(drop=True)


def kruskal_wallis_test(df, metric_col, segment_col):
    """
    Executa teste Kruskal-Wallis entre grupos definidos por segment_col.
    Pode receber o nome da coluna ou as séries de labels diretamente.
    """
    groups = [g[metric_col].dropna().values for _, g in df.groupby(segment_col, observed=True)]
    groups = [g for g in groups if len(g) > 0]

    if len(groups) < 2:
        return {'H': np.nan, 'p_value': np.nan, 'significativo': False, 'n_groups': len(groups)}

    h_stat, p_val = stats.kruskal(*groups)
    return {
        'H': h_stat,
        'p_value': p_val,
        'significativo': p_val < 0.05,
        'n_groups': len(groups)
    }


def mann_whitney_test(df, metric_col, segment_col, group_a, group_b):
    """
    Teste Mann-Whitney U entre dois grupos específicos.
    """
    if isinstance(segment_col, str):
        groups = df[segment_col]
    else:
        groups = segment_col

    a = df[groups == group_a][metric_col].dropna()
    b = df[groups == group_b][metric_col].dropna()

    if len(a) < 2 or len(b) < 2:
        return {'U': np.nan, 'p_value': np.nan, 'effect_size_r': np.nan, 'mean_a': np.nan, 'mean_b': np.nan}

    u_stat, p_val = stats.mannwhitneyu(a, b, alternative='two-sided')
    n = len(a) + len(b)
    z = stats.norm.ppf(1 - p_val / 2)
    r = z / np.sqrt(n)

    return {
        'U': u_stat,
        'p_value': p_val,
        'effect_size_r': abs(r),
        'n_a': len(a),
        'n_b': len(b),
        'mean_a': a.mean(),
        'mean_b': b.mean(),
    }


def spearman_correlation(df, col_a, col_b):
    """Calcula correlação de Spearman entre duas colunas."""
    valid = df[[col_a, col_b]].dropna()
    if len(valid) < 3:
        return {'rho': np.nan, 'p_value': np.nan}
    rho, p_val = stats.spearmanr(valid[col_a], valid[col_b])
    return {'rho': rho, 'p_value': p_val, 'n': len(valid)}
