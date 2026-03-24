from pathlib import Path

# ============================================================
# config.py — Configuração Central do Projeto
# Geocoding Quality Analysis: CNEFE 2022 vs BHMap (Gold Standard)
# ============================================================

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

OUTPUT_DIR = BASE_DIR / 'outputs'
FIG_DIR = OUTPUT_DIR / 'figures'
MAP_DIR = OUTPUT_DIR / 'maps'
TAB_DIR = OUTPUT_DIR / 'tables'

# Context layers
CONTEXT_DIR = RAW_DIR / 'bhmap_context'
REGIONAIS_SHP = CONTEXT_DIR / 'REGIONAL' / 'REGIONAL.shp'
BAIRROS_SHP = CONTEXT_DIR / 'BAIRRO_OFICIAL' / 'BAIRRO_OFICIAL.shp'
VILAS_FAVELAS_SHP = CONTEXT_DIR / 'VILA_FAVELA' / 'VILA_FAVELA.shp'
POP_BAIRRO_SHP = CONTEXT_DIR / 'POP_DOMIC_BAIRRO_2022' / 'POP_DOMIC_BAIRRO_2022.shp'

# v4 context layers
SETOR_CENSITARIO_SHP = CONTEXT_DIR / 'SETOR_CENSITARIO_2022' / 'SETOR_CENSITARIO_2022.shp'
TIPOLOGIA_USO_SHP = CONTEXT_DIR / 'TIPOLOGIA_USO_OCUPACAO_LOTE_2022' / 'TIPOLOGIA_USO_OCUPACAO_LOTE_2022.shp'
CLASSIFICACAO_VIARIA_SHP = CONTEXT_DIR / 'CLASSIFICACAO_VIARIA_11181' / 'CLASSIFICACAO_VIARIA_11181.shp'
DECLIVIDADE_SHP = CONTEXT_DIR / 'DECLIVIDADE_TRECHO_LOGRADOURO_2015' / 'DECLIVIDADE_TRECHO_LOGRADOURO_2015.shp'
ATIVIDADE_ECONOMICA_SHP = CONTEXT_DIR / 'ATIVIDADE_ECONOMICA' / 'ATIVIDADE_ECONOMICA.shp'
ZONA_IPTU_SHP = CONTEXT_DIR / 'ZONA_HOMOGENEA_IPTU' / 'ZONA_HOMOGENEA_IPTU.shp'
ZONEAMENTO_SHP = CONTEXT_DIR / 'ZONEAMENTO_11181' / 'ZONEAMENTO_11181.shp'

# Legacy aliases for older notebook cells
IPTU_SHP = ZONA_IPTU_SHP
LOTE_TIPOLOGIA_SHP = TIPOLOGIA_USO_SHP

# Ensure directories exist
for p in [RAW_DIR, PROCESSED_DIR, FIG_DIR, MAP_DIR, TAB_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# ============================================================
# Geoprocessing Constants
# ============================================================
TARGET_CRS = "EPSG:31983"    # SIRGAS 2000 / UTM zone 23S (Belo Horizonte)
ORIGINAL_CRS = "EPSG:4326"  # WGS84 (GPS / lat-lon padrão)

# ============================================================
# Matching Defaults
# ============================================================
MAX_SEARCH_RADIUS_METERS = 100
FUZZY_MATCH_THRESHOLD = 80
MCI_ALPHA = 0.5  # Peso da similaridade textual vs espacial

# ============================================================
# CNEFE Dictionaries
# ============================================================
ESPECIE_MAP = {
    1: 'Domicílio Particular',
    2: 'Domicílio Coletivo',
    3: 'Estab. Agropecuário',
    4: 'Estab. Ensino',
    5: 'Estab. Saúde',
    6: 'Outras Finalidades',
    7: 'Em Construção',
    8: 'Estab. Religioso',
}

TIPO_ESPECIE_MAP = {
    101: 'Casa',
    102: 'Casa de Vila/Condomínio',
    103: 'Apartamento',
    104: 'Outros',
}

NV_GEO_MAP = {
    1: 'Medido em campo',
    2: 'Estimado próximo',
    3: 'Estimado distante',
    4: 'Outro método',
    6: 'Sem medição',
}

# LCI weights based on NV_GEO_COORD (Davis & Fonseca, 2007 adaptation)
LCI_WEIGHTS_BY_NV_GEO = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.3, 6: 0.1}

# Completude: campos e pesos para cálculo de completude ISO 19157
COMPLETUDE_CAMPOS_PESOS = {
    'CEP':              1.5,
    'LOGRAD_NUM':       1.5,
    'COMPLEMENTO':      1.0,
    'DSC_LOCALIDADE':   0.5,
    'NV_GEO_COORD':     0.5,
}

# ============================================================
# Visualization Constants
# ============================================================
PALETA_ESPECIE = {
    'Domicílio Particular': '#3498db',
    'Domicílio Coletivo':   '#e74c3c',
    'Estab. Agropecuário':  '#2ecc71',
    'Estab. Ensino':        '#9b59b6',
    'Estab. Saúde':         '#1abc9c',
    'Outras Finalidades':   '#f39c12',
    'Em Construção':        '#95a5a6',
    'Estab. Religioso':     '#e67e22',
}

PALETA_TIPO_RESID = {
    'Casa': '#2980b9',
    'Apartamento': '#c0392b',
    'Casa de Vila/Condomínio': '#27ae60',
    'Outros': '#7f8c8d',
}

# Matplotlib global style
import matplotlib
matplotlib.rcParams.update({
    'figure.figsize': (12, 8),
    'figure.dpi': 150,
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'axes.spines.top': False,
    'axes.spines.right': False,
})
