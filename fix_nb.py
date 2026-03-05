import nbformat as nbf

with open('notebooks/01_setup_ingest.ipynb', 'r', encoding='utf-8') as f:
    nb = nbf.read(f, as_version=4)

new_source = """logger.info("Carregando bases filtradas Parquet geradas pelo DuckDB...")

# Load pre-filtered parquets using Pandas first (no geo metadata built-in)
df_cnefe = pd.read_parquet(config.CNEFE_PROCESSED_FILE)
df_bhmap = pd.read_parquet(config.BHMAP_PROCESSED_FILE)

# CNEFE uses 'wkt_geometry' column
gdf_cnefe_bh = gpd.GeoDataFrame(df_cnefe, geometry=gpd.GeoSeries.from_wkt(df_cnefe['wkt_geometry']), crs='EPSG:4674')

# BHMap might use 'wkt_geometry' or 'geometry'
bhmap_geom_col = 'wkt_geometry' if 'wkt_geometry' in df_bhmap.columns else 'geometry'
try:
    gdf_bhmap = gpd.GeoDataFrame(df_bhmap, geometry=gpd.GeoSeries.from_wkt(df_bhmap[bhmap_geom_col]), crs=config.DEFAULT_CRS)
except TypeError:
    # already geometry objects?
    gdf_bhmap = gpd.GeoDataFrame(df_bhmap, geometry=bhmap_geom_col, crs=config.DEFAULT_CRS)

# Reproject everything to exactly the same metric CRS for precise comparisons in the next steps
gdf_cnefe_bh = gdf_cnefe_bh.to_crs(config.DEFAULT_CRS)
gdf_bhmap = gdf_bhmap.to_crs(config.DEFAULT_CRS)

# Drop redundant wkt columns if any
for col in ['wkt_geometry']:
    if col in gdf_cnefe_bh.columns:
        gdf_cnefe_bh = gdf_cnefe_bh.drop(columns=[col])
    if col in gdf_bhmap.columns and col != gdf_bhmap._geometry_column_name:
        gdf_bhmap = gdf_bhmap.drop(columns=[col])

logger.info("Dados carregados e projetados no sistema métrico", 
            cnefe_crs=str(gdf_cnefe_bh.crs), 
            bhmap_crs=str(gdf_bhmap.crs))"""

for cell in nb.cells:
    if cell.cell_type == 'code' and 'gpd.GeoSeries.from_wkt' in cell.source:
        cell.source = new_source

with open('notebooks/01_setup_ingest.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
