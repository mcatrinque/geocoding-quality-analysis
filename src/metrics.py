"""
metrics.py — Métricas de Qualidade da Geocodificação
Davis & Fonseca (2007) + ISO 19157

Implementa: LCI, MCI, PCI, GCI, Completude, RMSE, CE90
"""
import numpy as np
import pandas as pd
from rapidfuzz import fuzz


# ============================================================
# LCI — Locating Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_lci(nv_geo_coord_series, weights_map=None):
    """
    Locating Certainty Indicator (LCI) conforme Davis & Fonseca (2007).
    Mede a certeza da coordenada produzida pelo geocodificador.

    No contexto do CNEFE 2022, o campo NV_GEO_COORD indica o método
    de obtenção da coordenada:
        1 = Medido em campo → LCI = 1.0
        2 = Estimado próximo → LCI = 0.8
        3 = Estimado distante → LCI = 0.5
        4 = Outro método → LCI = 0.3
        6 = Sem medição → LCI = 0.1

    Args:
        nv_geo_coord_series: Series com valores NV_GEO_COORD
        weights_map: Dicionário {nível: peso}

    Returns:
        Series com LCI scores (0.0 a 1.0)
    """
    if weights_map is None:
        weights_map = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.3, 6: 0.1}
    return nv_geo_coord_series.map(weights_map).fillna(0.1)


# ============================================================
# Completude — ISO 19157
# ============================================================
def calculate_completude(df, campos_pesos=None):
    """
    Indicador de Completude conforme ISO 19157.
    Avalia a presença/ausência dos atributos críticos do endereço.

    Args:
        df: DataFrame com registros de endereço
        campos_pesos: Dict {nome_coluna: peso}

    Returns:
        Series com scores de completude (0.0 a 1.0)
    """
    if campos_pesos is None:
        campos_pesos = {
            'CEP': 1.5,
            'LOGRAD_NUM': 1.5,
            'COMPLEMENTO': 1.0,
            'DSC_LOCALIDADE': 0.5,
            'NV_GEO_COORD': 0.5,
        }

    total_weight = sum(campos_pesos.values())
    scores = np.zeros(len(df))

    for col, weight in campos_pesos.items():
        if col in df.columns:
            presence = df[col].notna() & (df[col].astype(str).str.strip() != '')
            scores += presence.astype(float) * weight

    return scores / total_weight


# ============================================================
# MCI — Matching Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_mci(distance, textual_sim, max_dist=100.0, alpha=0.5):
    """
    Matching Certainty Indicator (MCI).
    Quantifica a confiança no pareamento CNEFE ↔ BHMap usando
    combinação linear de similaridade espacial e textual.

    MCI = α × Sim_textual + (1-α) × Sim_espacial

    Args:
        distance: Distância euclidiana em metros entre pares
        textual_sim: Similaridade textual (0 a 100, RapidFuzz)
        max_dist: Raio máximo de busca (default 100m)
        alpha: Peso da similaridade textual (default 0.5)

    Returns:
        Series/array com MCI scores (0.0 a 1.0)
    """
    spatial_sim = np.clip(1.0 - (distance / max_dist), 0.0, 1.0)
    textual_sim_norm = np.clip(textual_sim / 100.0, 0.0, 1.0)
    return (alpha * textual_sim_norm) + ((1 - alpha) * spatial_sim)


def calculate_textual_similarity(str1, str2):
    """
    Calcula similaridade textual entre strings de endereço via RapidFuzz.
    Usa token_sort_ratio para robustez contra reordenação de tokens.
    """
    if pd.isna(str1) or pd.isna(str2):
        return 0.0
    return fuzz.token_sort_ratio(str(str1).lower(), str(str2).lower())


# ============================================================
# PCI — Positional Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_pci(df, tipo_col='COD_TIPO_ESPECI', complemento_col='COMPLEMENTO',
                  vertical_score=0.5, horizontal_score=1.0):
    """
    Positional Certainty Indicator (PCI).
    Penaliza endereços verticalizados (apartamentos, edifícios) onde
    a coordenada do ponto não distingue a unidade exata.

    Usa COD_TIPO_ESPECI (103=Apartamento) e/ou padrões no COMPLEMENTO.

    Args:
        df: DataFrame
        tipo_col: Coluna com sub-tipo do endereço
        complemento_col: Coluna com complemento
        vertical_score: Score PCI para endereços verticais (default 0.5)
        horizontal_score: Score PCI para endereços horizontais (default 1.0)

    Returns:
        Series com PCI scores
    """
    is_vertical = pd.Series(False, index=df.index)

    # Via COD_TIPO_ESPECI (103 = Apartamento)
    if tipo_col in df.columns:
        is_vertical |= (df[tipo_col] == 103).fillna(False)

    # Via COMPLEMENTO (contém "APARTAMENTO", "EDIFÍCIO", "BLOCO", etc.)
    if complemento_col in df.columns:
        pattern = r'apartamento|edif[ií]cio|condom[ií]nio|bloco|sala|loja|andar|cobertura'
        is_vertical |= df[complemento_col].astype(str).str.contains(
            pattern, case=False, na=False
        )

    return np.where(is_vertical.values, vertical_score, horizontal_score)


# ============================================================
# GCI — Geocoding Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_gci(lci, mci, pci):
    """
    Geocoding Certainty Indicator: GCI = LCI × MCI × PCI
    Métrica composta que integra as três dimensões de certeza.
    """
    return lci * mci * pci


# ============================================================
# Métricas Posicionais
# ============================================================
def calculate_rmse(distances):
    """Root Mean Square Error das distâncias euclidianas."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.sqrt(np.mean(np.square(d)))


def calculate_ce90(distances):
    """Circular Error 90%: raio que contém 90% dos erros."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.percentile(d, 90)


def calculate_mae(distances):
    """Mean Absolute Error das distâncias."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.mean(np.abs(d))


def calculate_median_error(distances):
    """Erro mediano — mais robusto que RMSE a outliers."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.median(d)
