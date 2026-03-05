"""
Módulo de matching espacial e textual.

Implementa a lógica híbrida de cruzamento: busca espacial por R-Tree
(sjoin_nearest) seguida de scoring fuzzy (Jaro-Winkler / Token Sort via rapidfuzz)
para calcular o Match Certainty Indicator (MCI).
"""

import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz

from src.log_config import logger


def get_spatial_candidates(
    gdf_cnefe: gpd.GeoDataFrame,
    gdf_bhmap: gpd.GeoDataFrame,
    max_distance: float = 50.0
) -> gpd.GeoDataFrame:
    """
    Encontra candidatos dentro de um raio máximo (em metros) via R-Tree.

    Utiliza ``gpd.sjoin_nearest`` para encontrar, para cada ponto CNEFE,
    o vizinho mais próximo no BHMap dentro de ``max_distance``.

    Args:
        gdf_cnefe: GeoDataFrame do CNEFE (projetado em UTM).
        gdf_bhmap: GeoDataFrame do BHMap (projetado em UTM).
        max_distance: Raio máximo de busca em metros.

    Returns:
        GeoDataFrame com os pares candidatos e a coluna ``spatial_distance``.
    """
    logger.info("Starting Spatial Join (sjoin_nearest)", max_distance=max_distance)

    gdf_cnefe = gdf_cnefe.copy()
    gdf_bhmap = gdf_bhmap.copy()

    if 'id_cnefe' not in gdf_cnefe.columns:
        gdf_cnefe['id_cnefe'] = gdf_cnefe.index
    if 'id_bhmap' not in gdf_bhmap.columns:
        gdf_bhmap['id_bhmap'] = gdf_bhmap.index

    candidates = gpd.sjoin_nearest(
        gdf_cnefe,
        gdf_bhmap,
        how="left",
        max_distance=max_distance,
        distance_col="spatial_distance"
    )

    logger.info("Spatial Join completed", total_candidates=len(candidates))
    return candidates


def calculate_mci(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o Match Certainty Indicator (MCI) via fuzzy matching (Token Sort Ratio).

    Concatena as strings padronizadas do CNEFE e do BHMap e calcula a
    similaridade normalizada [0.0, 1.0] utilizando ``rapidfuzz.fuzz.token_sort_ratio``.

    Args:
        candidates_df: DataFrame de candidatos com colunas ``std_*``.

    Returns:
        DataFrame com a coluna ``MCI`` adicionada.
    """
    logger.info("Calculating Fuzzy String Matching (MCI)")

    if len(candidates_df) == 0:
        candidates_df['MCI'] = []
        return candidates_df

    # Construção vetorizada das strings CNEFE
    str_cnefe = (
        candidates_df['std_logradouro_completo']
        .fillna('').astype(str)
        .str.replace(',', '', regex=False).str.strip()
    )

    # Construção vetorizada das strings BHMap
    tipo = candidates_df['std_tipo_logradouro'].fillna('').astype(str).str.strip()
    nome = candidates_df['std_nome_logradouro'].fillna('').astype(str).str.strip()

    num_bhmap = candidates_df['std_numero'].copy()
    num_mask = num_bhmap.notna()
    num_bhmap.loc[num_mask] = (
        num_bhmap.loc[num_mask].astype(str)
        .str.replace('.0', '', regex=False).str.strip()
    )
    num_bhmap = num_bhmap.fillna('').astype(str)

    str_bhmap = (tipo + ' ' + nome + ' ' + num_bhmap).str.replace(',', '', regex=False).str.strip()

    # Máscara de validade
    valid_mask = (str_cnefe != '') & (str_bhmap != '')
    if 'index_right' in candidates_df.columns:
        valid_mask = valid_mask & candidates_df['index_right'].notna()

    cnefe_list = str_cnefe.tolist()
    bhmap_list = str_bhmap.tolist()
    valid_list = valid_mask.tolist()

    # Scoring via rapidfuzz
    mci_scores = [
        fuzz.token_sort_ratio(c, b) / 100.0 if v else 0.0
        for c, b, v in zip(cnefe_list, bhmap_list, valid_list)
    ]

    candidates_df['MCI'] = mci_scores
    logger.info("Fuzzy logic (MCI) calculation completed")
    return candidates_df


def resolve_best_match(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """
    Resolve a melhor correspondência para cada ponto CNEFE.

    Critérios de desempate (em ordem):
        1. Maior MCI (similaridade textual).
        2. Menor distância espacial.

    Args:
        candidates_df: DataFrame com múltiplos candidatos por ponto.

    Returns:
        DataFrame deduplicado com o melhor match por ``id_cnefe``.
    """
    logger.info("Resolving best matches from candidates")

    if 'id_cnefe' not in candidates_df.columns:
        candidates_df['id_cnefe'] = candidates_df.index

    resolved = candidates_df.sort_values(
        by=['id_cnefe', 'MCI', 'spatial_distance'],
        ascending=[True, False, True]
    )
    resolved = resolved.drop_duplicates(subset=['id_cnefe'], keep='first')
    resolved['MCI'] = resolved['MCI'].fillna(0.0)

    logger.info("Best match resolution completed", final_rows=len(resolved))
    return resolved
