#!/usr/bin/env python
# coding: utf-8

# # 01 Setup & Ingestão de Dados (via DuckDB ETL)
# 
# **Objetivo:** Carregar os dados hiper-rápidos parquet exportados pelo `etl_pipeline.py`. O DuckDB já cuidou de filtrar os 4.9GB do CNEFE apenas para Belo Horizonte e executar a normalização de strings em C++ vetorizado. Aqui no notebook, tratamos a etapa geográfica através do *GeoPandas*.
# 
# **Entradas (Parquet):**
# - `data/processed/cnefe_bh.parquet`
# - `data/processed/bhmap_enderecos.parquet`
# 
# **Saídas:**
# - `data/processed/cnefe_bh.parquet` (Atualizado com geometria reprojetada EPSG:31983)
# - `data/processed/bhmap_enderecos.parquet` (Atualizado com geometria reprojetada EPSG:31983)
# - `outputs/tables/01_basic_profile.csv`
# - `outputs/figures/01_spatial_overview.png`
# 
# **Dependências:** geopandas, pandas, matplotlib
# 
# **Hardware/Tempo Esperado:** Carga instantânea (< 2 segundos). RAM mínima necessária: 2GB.

# In[1]:


import sys
from pathlib import Path
import os

# Ensure root path is accessible to import src
os.chdir('..')
sys.path.append(os.getcwd())

get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')

import pandas as pd
import geopandas as gpd
from shapely import wkt
import matplotlib.pyplot as plt

from src import config
from src.logging import logger


# ## 1. Carregamento do Cache Parquet e Geometria

# In[2]:


logger.info("Carregando bases filtradas Parquet geradas pelo DuckDB...")

# Load pre-filtered parquets
df_cnefe = pd.read_parquet(config.CNEFE_PROCESSED_FILE)
df_bhmap = pd.read_parquet(config.BHMAP_PROCESSED_FILE)

# Convert WKT strings back to standard GeoPandas geometry
# The native crs for CNEFE is EPSG:4674 (SIRGAS 2000 lat/lon) based on the raw JSON file
# The native crs for BHMap is EPSG:31983 usually, let's assume default metric first
gdf_cnefe_bh = gpd.GeoDataFrame(df_cnefe, geometry=gpd.GeoSeries.from_wkt(df_cnefe['wkt_geometry']), crs='EPSG:4674')
gdf_bhmap = gpd.GeoDataFrame(df_bhmap, geometry=gpd.GeoSeries.from_wkt(df_bhmap['wkt_geometry']), crs=config.DEFAULT_CRS)

# Reproject everything to exactly the same metric CRS for precise comparisons in the next steps
gdf_cnefe_bh = gdf_cnefe_bh.to_crs(config.DEFAULT_CRS)
gdf_bhmap = gdf_bhmap.to_crs(config.DEFAULT_CRS)

# Drop the WKT columns to save space
gdf_cnefe_bh = gdf_cnefe_bh.drop(columns=['wkt_geometry'])
gdf_bhmap = gdf_bhmap.drop(columns=['wkt_geometry'])

logger.info("Dados carregados e projetados no sistema métrico", 
            cnefe_crs=str(gdf_cnefe_bh.crs), 
            bhmap_crs=str(gdf_bhmap.crs))


# ## 2. Visão do Esquema Canônico

# In[3]:


display(gdf_cnefe_bh[[c for c in gdf_cnefe_bh.columns if c.startswith('std_')]].head(3))
display(gdf_bhmap[[c for c in gdf_bhmap.columns if c.startswith('std_')]].head(3))


# ## 3. Profiling Estatístico Básico

# In[4]:


def generate_profile(gdf, name):
    stats = []
    canonical_cols = [c for c in gdf.columns if c.startswith('std_')]
    for col in canonical_cols:
        stats.append({
            'Dataset': name,
            'Field': col,
            'Total_Rows': len(gdf),
            'Missing_Count':  gdf[col].isna().sum() + (gdf[col] == '').sum(),
            'Unique_Values': gdf[col].nunique()
        })

    df = pd.DataFrame(stats)
    df['Missing_Percentage'] = round((df['Missing_Count'] / df['Total_Rows']) * 100, 2)
    return df

profile_cnefe = generate_profile(gdf_cnefe_bh, 'CNEFE')
profile_bhmap = generate_profile(gdf_bhmap, 'BHMap')
profile_df = pd.concat([profile_cnefe, profile_bhmap])

display(profile_df)


# ## 4. Re-Exportação Espacial (Save State)

# In[5]:


# Update Parquet files with native GeoParquet representation now that geometry is fixed
gdf_cnefe_bh.to_parquet(config.CNEFE_PROCESSED_FILE)
gdf_bhmap.to_parquet(config.BHMAP_PROCESSED_FILE)

profile_csv_path = config.TABLES_DIR / "01_basic_profile.csv"
profile_df.to_csv(profile_csv_path, index=False)
logger.info("Bases GeoParquet atualizadas via GeoPandas.")


# ## 5. Overview Espacial Gráfico

# In[6]:


fig, ax = plt.subplots(figsize=(10, 10), dpi=150)

gdf_bhmap.plot(ax=ax, markersize=1, color='blue', alpha=0.3, label='BHMap')
gdf_cnefe_bh.plot(ax=ax, markersize=1, color='orange', alpha=0.3, label='CNEFE')

ax.set_title("Visão Espacial: CNEFE vs BHMap em Belo Horizonte (UTM 23S)")
ax.legend(markerscale=10)
plt.axis('off')

config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
plt.savefig(config.FIGURES_DIR / "01_spatial_overview.png", bbox_inches='tight')
logger.info("Figura espacial gerada.")
plt.show()

