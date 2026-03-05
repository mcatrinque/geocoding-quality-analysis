"""
Módulo de configuração centralizada do projeto.

Define caminhos de diretórios, arquivos de entrada/saída,
sistemas de referência de coordenadas (CRS) e constantes globais.
"""

from pathlib import Path

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Diretórios de dados
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Arquivos de entrada (dados brutos)
CNEFE_RAW_FILE = RAW_DATA_DIR / "cnefe2022" / "qg_810_endereco_UF31.json"
BHMAP_RAW_FILE = RAW_DATA_DIR / "bhmap" / "bhmap.shp"
LIMITE_BH_RAW_FILE = RAW_DATA_DIR / "limite_bh.shp"

# Arquivos de saída (dados processados)
CNEFE_PROCESSED_FILE = PROCESSED_DATA_DIR / "cnefe_bh.parquet"
BHMAP_PROCESSED_FILE = PROCESSED_DATA_DIR / "bhmap_enderecos.parquet"

# Diretórios de outputs
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
MAPS_DIR = OUTPUTS_DIR / "maps"
REPORTS_DIR = OUTPUTS_DIR / "reports"

# Criação automática dos diretórios necessários
for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, TABLES_DIR, FIGURES_DIR, MAPS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Semente aleatória para reprodutibilidade
RANDOM_SEED = 42

# Sistemas de Referência de Coordenadas (CRS)
# EPSG:31983 — SIRGAS 2000 / UTM zona 23S (apropriado para BH; cálculos métricos)
# EPSG:4326  — WGS 84 (latitude/longitude padrão)
DEFAULT_CRS = "EPSG:31983"
LATLON_CRS = "EPSG:4326"

# Valor padrão para dados ausentes
FALLBACK_MISSING_VALUE = "MISSING_DATA"