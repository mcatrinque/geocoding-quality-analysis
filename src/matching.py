import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz
from src.logging import logger

def get_spatial_candidates(gdf_cnefe: gpd.GeoDataFrame, gdf_bhmap: gpd.GeoDataFrame, max_distance: float = 50.0) -> gpd.GeoDataFrame:
    """
    Finds candidates within a specified max_distance (in meters)
    using R-Tree indexing via GeoPandas sjoin_nearest.
    """
    logger.info("Starting Spatial Join (sjoin_nearest)", max_distance=max_distance)
    
    gdf_cnefe = gdf_cnefe.copy()
    gdf_bhmap = gdf_bhmap.copy()
    
    if 'id_cnefe' not in gdf_cnefe.columns:
        gdf_cnefe['id_cnefe'] = gdf_cnefe.index
    if 'id_bhmap' not in gdf_bhmap.columns:
        gdf_bhmap['id_bhmap'] = gdf_bhmap.index

    # Use GeoPandas sjoin_nearest
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
    Calculates the Matching Certainty Indicator (MCI) using Fuzzy Logic (Levenshtein Token Sort)
    on the standardized address strings. Optimized with vectorized string concatenation.
    """
    logger.info("Calculating Fuzzy String Matching (MCI)")
    
    if len(candidates_df) == 0:
        candidates_df['MCI'] = []
        return candidates_df
        
    # Vectorized construction for CNEFE strings
    str_cnefe = candidates_df['std_logradouro_completo'].fillna('').astype(str).str.replace(',', '', regex=False).str.strip()
    
    # Vectorized construction for BHMap strings
    tipo = candidates_df['std_tipo_logradouro'].fillna('').astype(str).str.strip()
    nome = candidates_df['std_nome_logradouro'].fillna('').astype(str).str.strip()
    
    num_bhmap = candidates_df['std_numero'].copy()
    num_mask = num_bhmap.notna()
    num_bhmap.loc[num_mask] = num_bhmap.loc[num_mask].astype(str).str.replace('.0', '', regex=False).str.strip()
    num_bhmap = num_bhmap.fillna('').astype(str)
    
    str_bhmap = (tipo + ' ' + nome + ' ' + num_bhmap).str.replace(',', '', regex=False).str.strip()
    
    # Mask where either string is empty or spatial join failed
    valid_mask = (str_cnefe != '') & (str_bhmap != '')
    if 'index_right' in candidates_df.columns:
        valid_mask = valid_mask & candidates_df['index_right'].notna()
        
    # Extract as numpy arrays / lists for fast iteration
    cnefe_list = str_cnefe.tolist()
    bhmap_list = str_bhmap.tolist()
    valid_list = valid_mask.tolist()
    
    # List comprehension for rapidfuzz
    mci_scores = [
        fuzz.token_sort_ratio(c, b) / 100.0 if v else 0.0 
        for c, b, v in zip(cnefe_list, bhmap_list, valid_list)
    ]
    
    candidates_df['MCI'] = mci_scores
    logger.info("Fuzzy logic (MCI) calculation completed")
    return candidates_df

def resolve_best_match(candidates_df: pd.DataFrame) -> pd.DataFrame:
    """
    For CNEFE points with multiple candidates within the buffer, 
    resolves the best one by picking the highest MCI.
    If tied on MCI, picks the closest spatial distance.
    """
    logger.info("Resolving best matches from candidates")
    
    if 'id_cnefe' not in candidates_df.columns:
        candidates_df['id_cnefe'] = candidates_df.index
        
    resolved = candidates_df.sort_values(
        by=['id_cnefe', 'MCI', 'spatial_distance'], 
        ascending=[True, False, True]
    )
    resolved = resolved.drop_duplicates(subset=['id_cnefe'], keep='first')
    
    # Fill remaining NaNs for spatial distance or MCI (i.e. those with NO match within 50m)
    resolved['MCI'] = resolved['MCI'].fillna(0.0)
    
    logger.info("Best match resolution completed", final_rows=len(resolved))
    return resolved
