"""
metrics.py — Métricas de Qualidade da Geocodificação
Davis & Fonseca (2007) + ISO 19157

Implementa: LCI, MCI, PCI, GCI, Completude, RMSE, CE90
Métricas de coordenada (intrínsecas): CCR, CDI, DRS, PCI_empirico
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


# ============================================================
# Métricas de Coordenada — qualidade intrínseca do ponto no espaço
# Complementam as métricas de endereço (MCI/GCI) com avaliação
# da coordenada como objeto geográfico, independente de referência externa.
# ============================================================

def calculate_cdi(gdf, coord_precision_m=1):
    """
    CDI — Coordinate Duplication Index.
    Conta quantos registros compartilham a mesma coordenada (arredondada
    à precisão dada em metros). Coordenadas compartilhadas indicam
    estimativa em massa (centróide de quadra, ponto de rua) em vez de
    medição individual.

    Valores: n >= 1. CDI=1 → coordenada única (boa). CDI=N → N registros
    no mesmo ponto (estimativa).

    Retorna duas Series:
        cdi        : contagem bruta de registros no mesmo ponto
        pci_empirico: 1/cdi ∈ (0, 1] — substituto empírico para PCI arbitrário

    Args:
        gdf: GeoDataFrame com geometria UTM (metros)
        coord_precision_m: arredondamento em metros (default=1m)

    Returns:
        DataFrame com colunas [cdi, pci_empirico] no mesmo índice de gdf
    """
    x = (gdf.geometry.x / coord_precision_m).round().astype(int)
    y = (gdf.geometry.y / coord_precision_m).round().astype(int)
    coord_key = x.astype(str) + "_" + y.astype(str)

    cdi = coord_key.map(coord_key.value_counts())
    pci_empirico = (1.0 / cdi).clip(upper=1.0)

    return pd.DataFrame({'cdi': cdi, 'pci_empirico': pci_empirico}, index=gdf.index)


def calculate_ccr(gdf_cnefe, gdf_setores, setor_col_cnefe='COD_SETOR',
                  setor_col_poly='COD_SETOR', normalize_setor=True):
    """
    CCR — Coordinate Containment Rate (por registro).
    Verifica se a coordenada do CNEFE cai dentro do polígono do setor
    censitário declarado no campo COD_SETOR. Discrepância indica erro
    topológico na coordenada ou atribuição incorreta de setor.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM, com COD_SETOR como atributo)
        gdf_setores: GeoDataFrame dos setores censitários (polígonos UTM)
        setor_col_cnefe: coluna em gdf_cnefe com código do setor declarado
        setor_col_poly: coluna em gdf_setores com código do setor
        normalize_setor: remove sufixo 'P' do CNEFE (formato IBGE vs BHMap)

    Returns:
        Series booleana `within_declared_setor` (True=OK, False=erro topológico)
    """
    import geopandas as gpd

    # Spatial join: descobre em qual setor a coordenada realmente cai
    setores_proj = gdf_setores[[setor_col_poly, 'geometry']].copy()
    setores_proj = setores_proj.rename(columns={setor_col_poly: 'setor_real'})

    joined = gpd.sjoin(
        gdf_cnefe[[setor_col_cnefe, 'geometry']],
        setores_proj,
        how='left',
        predicate='within'
    )

    setor_declarado = joined[setor_col_cnefe].astype(str).str.strip()
    if normalize_setor:
        # CNEFE usa sufixo 'P' (e.g. '310620005630498P'); shapefile não usa
        setor_declarado = setor_declarado.str.rstrip('P').str.rstrip('S')

    setor_real = joined['setor_real'].astype(str).str.strip()

    within = (setor_declarado == setor_real)
    within = within.reindex(gdf_cnefe.index)
    within = within.fillna(False)
    return within


def calculate_drs(gdf_cnefe, gdf_vias, batch_size=50_000):
    """
    DRS — Distance to Road Segment (metros).
    Distância de cada ponto CNEFE ao segmento de via mais próximo.
    Alta DRS indica ponto em área sem logradouro próximo (morro, praça,
    área industrial) ou coordenada deslocada da via declarada.

    Usa sjoin_nearest contra a rede viária (LineStrings UTM).
    Processado em lotes para controlar uso de memória.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM)
        gdf_vias: GeoDataFrame de vias (LineStrings UTM)
        batch_size: tamanho do lote para processamento

    Returns:
        Series float com distância em metros, mesmo índice de gdf_cnefe
    """
    import geopandas as gpd
    from tqdm.auto import tqdm

    vias = gdf_vias[['geometry']].copy()
    results = []
    idx_list = gdf_cnefe.index.tolist()

    for start in tqdm(range(0, len(idx_list), batch_size), desc="  Distância às vias", unit="lote"):
        batch_idx = idx_list[start:start + batch_size]
        batch = gdf_cnefe.loc[batch_idx, ['geometry']]
        joined = gpd.sjoin_nearest(batch, vias, how='left', distance_col='drs')
        # sjoin_nearest pode duplicar se houver empate; manter o menor
        joined = joined[~joined.index.duplicated(keep='first')]
        results.append(joined['drs'])

    drs_series = pd.concat(results)
    drs_series = drs_series.reindex(gdf_cnefe.index)
    return drs_series


def calculate_csi(gdf_cnefe, gdf_setores, setor_col_cnefe='COD_SETOR',
                  setor_col_poly='COD_SETOR', normalize_setor=True):
    """
    CSI — Coordinate Spatial Isolation (metros).
    Distância do ponto CNEFE ao centróide do seu setor censitário declarado.
    Pontos muito distantes do centróide de seu setor são candidatos a erro
    de atribuição ou deslocamento grosseiro de coordenada.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM)
        gdf_setores: GeoDataFrame dos setores (UTM, polígonos)
        normalize_setor: remove sufixo 'P' do CNEFE (formato IBGE vs BHMap)

    Returns:
        Series float com distância ao centróide do setor (metros)
    """
    setores_centroids = gdf_setores[[setor_col_poly, 'geometry']].copy()
    setores_centroids['centroid'] = setores_centroids.geometry.centroid
    centroid_map = setores_centroids.set_index(setor_col_poly)['centroid'].to_dict()

    setor_declared = gdf_cnefe[setor_col_cnefe].astype(str).str.strip()
    if normalize_setor:
        setor_declared = setor_declared.str.rstrip('P').str.rstrip('S')

    centroids = setor_declared.map(centroid_map)
    valid_mask = centroids.notna()
    distances = pd.Series(np.nan, index=gdf_cnefe.index)

    if valid_mask.any():
        pts = gdf_cnefe.loc[valid_mask, 'geometry']
        ctrs = centroids[valid_mask]
        import geopandas as gpd
        ctrs_gs = gpd.GeoSeries(ctrs, crs=gdf_cnefe.crs)
        distances[valid_mask] = pts.distance(ctrs_gs)

    return distances
