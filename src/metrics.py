import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_completeness(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Calculates the percentage of non-null and non-empty values for a given list of columns.
    
    Args:
        df (pd.DataFrame): The dataframe to analyze.
        columns (list): List of column names to check completeness for.
    
    Returns:
        pd.DataFrame: A dataframe with completeness statistics.
    """
    stats = []
    total_rows = len(df)
    
    if total_rows == 0:
        return pd.DataFrame()
        
    for col in columns:
        if col not in df.columns:
            continue
            
        # Consider None, NaN, empty strings, and strings with only spaces as missing
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
    Calculates the Root Mean Square Error (RMSE) of the spatial distance (positional error).
    
    Args:
        df (pd.DataFrame): The dataframe containing the matches.
        error_col (str): The column representing the distance error in meters.
        
    Returns:
        float: The RMSE value in meters.
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
    Generates a concise quality summary focusing on matches at or above a given MCI threshold.
    """
    high_certainty = df[df['MCI'] >= mci_threshold]
    
    return {
        'total_records': len(df),
        'high_certainty_matches': len(high_certainty),
        'high_certainty_percent': round((len(high_certainty) / len(df)) * 100, 2) if len(df) > 0 else 0,
        'average_positional_error_m': round(high_certainty['spatial_distance'].mean(), 2) if 'spatial_distance' in high_certainty else np.nan,
        'positional_rmse_m': calculate_positional_rmse(high_certainty)
    }
