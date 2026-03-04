import duckdb
from pathlib import Path
import time
import pandas as pd
pd.options.mode.string_storage = "python"
import tempfile
from src import config
from src.logging import logger

def clean_text_df(series):
    import unicodedata
    import re
    def _clean(text):
        if pd.isna(text) or not isinstance(text, str):
            return ""
        text = text.strip().upper()
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        return re.sub(r'\s+', ' ', text)
    return series.apply(_clean)

def run_etl():
    """
    Executes a Hybrid Out-of-Core ETL Pipeline.
    """
    start_time = time.time()
    logger.info("Starting Hybrid DuckDB ETL Pipeline")
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=':memory:')
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")

    # Use cross-platform system temp directory securely
    temp_dir = Path(tempfile.gettempdir()) / "geocoding_analysis"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_cnefe = temp_dir / "temp_cnefe.parquet"
    temp_bhmap = temp_dir / "temp_bhmap.parquet"

    # 1. DuckDB Fast Extraction
    logger.info("1/5 - DuckDB: Extracting and Filtering CNEFE 2022")
    cnefe_query = f"""
        COPY (
            SELECT 
                LOGRAD_NUM, COMPLEMENTO, DSC_LOCALIDADE, CEP, ST_AsText(geom) AS wkt_geometry
            FROM st_read('{config.CNEFE_RAW_FILE}')
            WHERE COD_MUNICIPIO = '3106200'
        ) TO '{temp_cnefe}' (FORMAT PARQUET);
    """
    con.execute(cnefe_query)

    logger.info("2/5 - GeoPandas: Extracting BHMap Endereços (Latin1 Encoding)")
    import geopandas as gpd
    gdf_bhmap_raw = gpd.read_file(config.BHMAP_RAW_FILE, encoding='latin1', engine='fiona')
    gdf_bhmap_raw = gdf_bhmap_raw[['SIGLA_TIPO', 'NOME_LOGRA', 'NUMERO_IMO', 'LETRA_IMOV', 'NOME_BAIRR', 'CEP', 'geometry']]
    gdf_bhmap_raw['wkt_geometry'] = gdf_bhmap_raw.geometry.apply(lambda geom: geom.wkt if geom else None)
    gdf_bhmap_raw = gdf_bhmap_raw.drop(columns=['geometry'])
    # Write fast flat parquet
    pd.DataFrame(gdf_bhmap_raw).to_parquet(temp_bhmap)
    del gdf_bhmap_raw
    con.close()

    # 2. Pandas Text Normalization
    logger.info("3/5 - Pandas: Normalizing CNEFE strings")
    df_cnefe = pd.read_parquet(temp_cnefe)
    df_cnefe['std_logradouro_completo'] = clean_text_df(df_cnefe.get('LOGRAD_NUM', pd.Series(dtype=str)))
    df_cnefe['std_complemento'] = clean_text_df(df_cnefe.get('COMPLEMENTO', pd.Series(dtype=str)))
    df_cnefe['std_bairro'] = clean_text_df(df_cnefe.get('DSC_LOCALIDADE', pd.Series(dtype=str)))
    df_cnefe['std_cep'] = clean_text_df(df_cnefe.get('CEP', pd.Series(dtype=str)))
    df_cnefe['std_municipio'] = 'BELO HORIZONTE'
    df_cnefe['std_uf'] = 'MG'

    logger.info("4/5 - Pandas: Normalizing BHMap strings")
    df_bhmap = pd.read_parquet(temp_bhmap)
    df_bhmap['std_tipo_logradouro'] = clean_text_df(df_bhmap.get('SIGLA_TIPO', pd.Series(dtype=str)))
    df_bhmap['std_nome_logradouro'] = clean_text_df(df_bhmap.get('NOME_LOGRA', pd.Series(dtype=str)))
    df_bhmap['std_numero'] = clean_text_df(df_bhmap.get('NUMERO_IMO', pd.Series(dtype=str)))
    df_bhmap['std_complemento_letra'] = clean_text_df(df_bhmap.get('LETRA_IMOV', pd.Series(dtype=str)))
    df_bhmap['std_bairro'] = clean_text_df(df_bhmap.get('NOME_BAIRR', pd.Series(dtype=str)))
    df_bhmap['std_cep'] = clean_text_df(df_bhmap.get('CEP', pd.Series(dtype=str)))
    df_bhmap['std_municipio'] = 'BELO HORIZONTE'
    df_bhmap['std_uf'] = 'MG'

    logger.info("5/5 - Exporting Canonicals to PROCESSED directory")
    df_cnefe.to_parquet(config.CNEFE_PROCESSED_FILE)
    df_bhmap.to_parquet(config.BHMAP_PROCESSED_FILE)
    
    elapsed = time.time() - start_time
    logger.info(f"Hybrid ETL Pipeline finished in {elapsed:.2f} seconds.")

if __name__ == "__main__":
    run_etl()