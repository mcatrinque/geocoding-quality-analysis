from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Inputs
CNEFE_RAW_FILE = RAW_DATA_DIR / "cnefe2022" / "qg_810_endereco_UF31.json"
BHMAP_RAW_FILE = RAW_DATA_DIR / "bhmap" / "bhmap.shp"
LIMITE_BH_RAW_FILE = RAW_DATA_DIR / "limite_bh.shp"

# Outputs
CNEFE_PROCESSED_FILE = PROCESSED_DATA_DIR / "cnefe_bh.parquet"
BHMAP_PROCESSED_FILE = PROCESSED_DATA_DIR / "bhmap_enderecos.parquet"

# Output directories
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
MAPS_DIR = OUTPUTS_DIR / "maps"
REPORTS_DIR = OUTPUTS_DIR / "reports"

# Create directories if they don't exist
for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, TABLES_DIR, FIGURES_DIR, MAPS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Global settings
RANDOM_SEED = 42

# Coordinate Reference System (CRS)
# EPSG:31983 is SIRGAS 2000 / UTM zone 23S (appropriated for Belo Horizonte, Brazil for metric distance calculations)
# EPSG:4326 is WGS 84 (standard longitude/latitude)
DEFAULT_CRS = "EPSG:31983"
LATLON_CRS = "EPSG:4326"

# Default fallback values for missing data analysis
FALLBACK_MISSING_VALUE = "MISSING_DATA"