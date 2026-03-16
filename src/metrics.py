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


def categorize_cnefe_species(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica cada registro do CNEFE em categorias analíticas baseadas em espécie e tipo.

    Mapeamento:
    - Residencial Horizontal: Espécie 1 (Particular) + Tipo 101/102 (Casa/Vila)
    - Residencial Vertical: Espécie 1 (Particular) + Tipo 103 (Apartamento)
    - Comercial e Serviços: Espécie 8 (Outras finalidades)
    - Serviço Público e Social: Espécie 4, 5 ou 6 (Ensino, Saúde, Religioso)
    - Outros: Outros códigos de espécie ou tipo.

    Args:
        df: DataFrame contendo COD_ESPECIE e COD_TIPO_ESPECI.

    Returns:
        DataFrame com a coluna 'categoria_analitica' adicionada.
    """
    def _get_cat(row):
        try:
            esp = int(float(row.get('COD_ESPECIE'))) if row.get('COD_ESPECIE') not in [None, '', 'nan'] else None
        except (ValueError, TypeError):
            esp = None
            
        try:
            tipo = int(float(row.get('COD_TIPO_ESPECI'))) if row.get('COD_TIPO_ESPECI') not in [None, '', 'nan'] else None
        except (ValueError, TypeError):
            tipo = None
        
        # Particular (Residencial)
        if esp == 1:
            if tipo in [101, 102]:
                return 'Residencial Horizontal'
            elif tipo == 103:
                return 'Residencial Vertical'
            return 'Residencial Outros'
        
        # Comercial/Serviços
        if esp == 8:
            return 'Comercial e Servicos'
        
        # Público/Social
        if esp in [4, 5, 6]:
            return 'Servico Publico/Social'
        
        # Unidade em Construção
        if esp == 7:
            return 'Unidade em Construcao'
        
        # Domicílio Coletivo
        if esp == 2:
            return 'Domicilio Coletivo'
            
        return 'Outros'

    df = df.copy()
    df['categoria_analitica'] = df.apply(_get_cat, axis=1)
    return df


def infer_bhmap_typology(df: pd.DataFrame) -> pd.DataFrame:
    """
    Infere a tipologia (Horizontal/Vertical) no BHMap baseada na densidade de endereços.
    
    Lógica: Coordenadas com mais de um endereço são classificadas como 'Vertical',
    indicando edifícios de apartamentos ou salas comerciais.
    
    Args:
        df: DataFrame do BHMap (contendo geometry).
        
    Returns:
        DataFrame com a coluna 'tipologia_bhmap' adicionada.
    """
    df = df.copy()
    # Identifica duplicatas espaciais (tenta geometry ou wkt_geometry)
    geo_col = 'geometry' if 'geometry' in df.columns else 'wkt_geometry'
    
    if geo_col not in df.columns:
        # Fallback para não quebrar se não houver coluna espacial
        df['tipologia_bhmap'] = 'Horizontal'
        df['address_count'] = 1
        return df

    counts = df.groupby(geo_col).size().reset_index(name='address_count')
    counts['tipologia_bhmap'] = counts['address_count'].apply(
        lambda x: 'Vertical' if x > 1 else 'Horizontal'
    )
    
    return df.merge(counts[[geo_col, 'tipologia_bhmap', 'address_count']], on=geo_col, how='left')


def calculate_match_rate_by_category(df_cnefe: pd.DataFrame, matched_ids: List[Any]) -> pd.DataFrame:
    """
    Calcula a taxa de pareamento (Matching Rate) para cada categoria do CNEFE.
    
    Args:
        df_cnefe: DataFrame original do CNEFE com categoria_analitica.
        matched_ids: Lista de identificadores únicos do CNEFE que foram pareados.
        
    Returns:
        DataFrame com colunas Category, Total, Matched, and Match Rate (%).
    """
    df_cnefe = df_cnefe.copy()
    df_cnefe['is_matched'] = df_cnefe['id_cnefe'].isin(matched_ids)
    
    summary = df_cnefe.groupby('categoria_analitica').agg(
        Total=('id_cnefe', 'count'),
        Matched=('is_matched', 'sum')
    ).reset_index()
    
    summary['Match Rate (%)'] = (summary['Matched'] / summary['Total'] * 100).round(2)
    return summary.rename(columns={'categoria_analitica': 'Category'})


def calculate_ce90(df: pd.DataFrame, error_col: str = 'spatial_distance') -> float:
    """
    Calcula o Circular Error 90% (CE90) da distância posicional em metros.
    Representa o raio que engloba 90% dos erros posicionais medidos.
    """
    if error_col not in df.columns or len(df) == 0:
        return np.nan

    valid_errors = df[error_col].dropna()
    if len(valid_errors) == 0:
        return np.nan

    ce90 = float(np.percentile(valid_errors.abs(), 90))
    return round(ce90, 2)


def categorize_formal_informal_toponymy(df: pd.DataFrame, street_col: str = 'std_tipo_logradouro') -> pd.DataFrame:
    """
    Classifica o tipo de logradouro em Formal ou Informal.
    Formal: RUA, AVENIDA, PRACA, RODOVIA, etc.
    Informal: BECO, VILA, ESCADARIA, TRAVESSA, VIELA, ALPE, etc.
    """
    df = df.copy()
    if street_col not in df.columns:
        df['toponimia_formalidade'] = 'Desconhecido'
        return df

    informal_types = ['BEC', 'VIL', 'ESC', 'TRA', 'VIE', 'PAS', 'AL', 'CAM']
    formality_map = lambda x: 'Informal' if str(x).strip().upper() in informal_types else 'Formal'
    
    df['toponimia_formalidade'] = df[street_col].apply(formality_map)
    return df


def calculate_pci(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o Positional Certainty Index (PCI) empírico, baseado na tipologia inferida.
    De acordo com Davis Jr., incerteza posicional baseada na consolidação de geometrias.
    - Horizontal (Isolado/Próximo Lote único): PCI = 1.0
    - Vertical (Adensamento em centroides/face de quadra): PCI = 0.5
    """
    df = df.copy()
    if 'tipologia_bhmap' not in df.columns:
        df = infer_bhmap_typology(df)
        
    df['PCI'] = df['tipologia_bhmap'].apply(lambda x: 1.0 if x == 'Horizontal' else 0.5)
    return df
