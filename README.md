# Análise de Qualidade e Incerteza de Dados Geoespaciais

**Estudo Empírico do CNEFE 2022 frente ao BHMap Endereços**

Repositório oficial da Dissertação de Mestrado em Ciência da Computação — UFMG.

---

## Introdução

A geocodificação — processo de converter endereços textuais em coordenadas geográficas — é fundamental para políticas públicas, logística, saúde e planejamento urbano. Contudo, as bases de endereços brasileiras possuem lacunas estruturais que propagam incertezas nos sistemas de informação geográfica (GIS) que as consomem.

Este projeto avalia empiricamente a **qualidade** e a **incerteza** dos dados de geocodificação do **Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE 2022)** do IBGE, utilizando a base municipal **BHMap Endereços** (Belo Horizonte — MG) como *Gold Standard* de referência.

A metodologia segue o arcabouço de Davis & Fonseca (2007), estruturando a análise em torno dos indicadores de certeza **PCI**, **MCI**, **LCI** e **GCI**, e incorporando técnicas estadísticas avançadas de autocorrelação espacial (Moran / LISA) e regressão multivariada (OLS) para quantificar os fatores urbanos que influenciam a degradação da acurácia posicional.

## Objetivos

1. **Completude**: Quantificar lacunas e taxas de preenchimento dos atributos do CNEFE 2022.
2. **Acurácia Posicional**: Mensurar o erro posicional médio (RMSE) entre pares de endereços geocodificados.
3. **Incerteza (MCI)**: Modelar a certeza de correspondência via matching espacial (R-Tree) + fuzzy textual (Token Sort Ratio).
4. **Autocorrelação Espacial**: Identificar clusters de erro via Moran's I e LISA.
5. **Fatores Socio-Espaciais**: Investigar se variáveis urbanas (informalidade, conurbação, complexidade viária, adensamento) explicam a degradação da qualidade.

---

## Metodologia

### Pipeline de Dados

O fluxo completo de processamento é reprodutível via um único comando. A arquitetura segue o padrão ETL → Matching → Análise:

```
data/raw/cnefe2022/*.json ─┐
                           ├──► etl_pipeline.py (DuckDB) ──► data/processed/*.parquet
data/raw/bhmap/*.shp ──────┘
                                        │
                            ┌───────────┘
                            ▼
              NB 01: Setup & Ingestão (reprojeção UTM 23S)
                            │
                            ▼
              NB 02: Matching Híbrido (R-Tree + RapidFuzz)
                            │
                            ▼
              data/processed/cnefe_match_bhmap.parquet
                            │
              ┌─────────────┼─────────────┐─────────────┐
              ▼             ▼             ▼             ▼
          NB 03          NB 04         NB 05         NB 06
        Completude   Acurácia      ESDA/LISA    Socio-Espacial
        (missingno)  (Violin/      (PySAL/      (geobr/osmnx/
                      Seaborn)      Folium)      OLS)
```

### Técnicas Utilizadas

| Etapa | Técnica | Biblioteca |
|---|---|---|
| Extração | SQL analítico sobre JSON massivo (5.5 GB) | DuckDB |
| Normalização | Remoção de diacríticos, uppercase, colapso de espaços | Pandas / unicodedata |
| Busca Espacial | R-Tree (sjoin_nearest, raio de 50m) | GeoPandas |
| Matching Textual | Token Sort Ratio (Levenshtein) | RapidFuzz |
| EDA | Matriz de nulidade, gráficos interativos | missingno, Plotly |
| Distribuição de Erro | Histograma com marginal Violin, Pairplot | Plotly, Seaborn |
| Consistência Semântica | Matriz de confusão normalizada (tipo de logradouro) | Plotly |
| Autocorrelação Global | I de Moran (permutação p < 0.05) | PySAL / esda |
| Clusters Locais | LISA (High-High, Low-Low) | PySAL / splot / Folium |
| Hexbin Maps | Densidade hexagonal sobre CartoDB | Plotly |
| Fronteiras Municipais | Distância ao limite municipal (efeito de borda) | geobr |
| Informalidade Urbana | Aglomerados subnormais do IBGE | geobr |
| Complexidade Viária | Interseções por km² da malha OSM | OSMnx |
| Regressão Espacial | OLS multivariado (StandardScaler) | statsmodels / sklearn |

---

## Estrutura do Repositório

```
geocoding-quality-analysis/
│
├── data/
│   ├── raw/                          # Dados brutos (CNEFE JSON + BHMap Shapefile)
│   └── processed/                    # Parquets processados (ETL + matching)
│
├── notebooks/
│   ├── 01_setup_ingest.ipynb         # Ingestão e reprojeção geográfica
│   ├── 02_address_matching.ipynb     # Motor híbrido de pareamento
│   ├── 03_completeness_analysis.ipynb # Análise de completude (missingno + Plotly)
│   ├── 04_quality_and_accuracy.ipynb  # Acurácia posicional (Violin + Confusão)
│   ├── 05_spatial_uncertainty_viz.ipynb # ESDA: Moran, LISA, Hexbin, Folium
│   └── 06_socio_spatial_vulnerability.ipynb # Regressão OLS socio-espacial
│
├── src/
│   ├── config.py                     # Configuração centralizada (paths, CRS)
│   ├── etl_pipeline.py               # Pipeline ETL (DuckDB + Pandas)
│   ├── matching.py                   # Motor de matching espacial + fuzzy
│   ├── metrics.py                    # Métricas de qualidade (RMSE, completude, MCI)
│   ├── maps.py                       # Visualizações cartográficas (KDE, barras)
│   └── log_config.py                 # Logging estruturado (structlog)
│
├── outputs/
│   ├── figures/                      # Gráficos exportados (HTML interativos + PNG)
│   ├── maps/                         # Mapas gerados
│   └── tables/                       # Tabelas de resultados
│
├── references/                       # Artigos de referência da dissertação
├── tasks.py                          # Orquestrador de tarefas (PyInvoke)
├── requirements.txt                  # Dependências Python
└── .gitignore
```

---

## Como Executar

O projeto utiliza [PyInvoke](https://www.pyinvoke.org/) para orquestrar todas as etapas do pipeline de forma reprodutível.

### Pré-requisitos

- Python 3.10+
- Os dados brutos devem ser colocados manualmente em `data/raw/`:
  - **CNEFE 2022 (MG)**: `data/raw/cnefe2022/qg_810_endereco_UF31.json` — baixar do [portal do IBGE](https://www.ibge.gov.br/estatisticas/downloads-estatisticas.html).
  - **BHMap Endereços**: `data/raw/bhmap/bhmap.shp` — baixar do [portal de dados abertos da PBH](https://dados.pbh.gov.br/).

### Instalação

```bash
# Criar e ativar ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# Instalar dependências e verificar dados
pip install -r requirements.txt
inv setup
```

### Comandos Disponíveis

| Comando | Descrição |
|---|---|
| `inv setup` | Instala dependências e verifica integridade dos dados brutos. |
| `inv clean` | Remove outputs e dados processados para um estado limpo. |
| `inv etl` | Executa a extração e normalização via DuckDB → Parquet. |
| `inv match` | Roda os notebooks de ingestão (01) e matching (02). |
| `inv analyze` | Roda os notebooks analíticos (03–06), gerando gráficos e mapas. |
| `inv all` | **Pipeline completo** (setup → clean → etl → match → analyze). |

Para reproduzir toda a dissertação do zero:

```bash
inv all
```

Os gráficos interativos serão exportados em `outputs/figures/` (HTML e PNG).

---

## Notebooks

### 01 — Setup & Ingestão
Carrega os Parquets do ETL, aplica a reprojeção para SIRGAS 2000 / UTM 23S (`EPSG:31983`) e gera um overview espacial dos dados sobre o município de Belo Horizonte.

### 02 — Matching Híbrido
Implementa o motor de pareamento em duas etapas: (1) busca espacial via R-Tree com raio de 50 metros e (2) scoring fuzzy via Token Sort Ratio (RapidFuzz). Calcula o **Match Certainty Indicator (MCI)** normalizado [0, 1] e resolve desempates por proximidade espacial.

### 03 — Análise de Completude
Avalia a completude estrutural dos atributos do CNEFE utilizando a biblioteca `missingno` (Nullity Matrix) e gráficos interativos Plotly. Quantifica endereços órfãos (MCI = 0) e taxas de preenchimento por campo.

### 04 — Qualidade e Acurácia Posicional
Foca nos registros de alta certeza (MCI ≥ 0.8) para mensurar o RMSE posicional. Inclui histograma com marginal Violin (Plotly), matriz de dispersão multivariada (Seaborn Pairplot) e matriz de confusão semântica normalizada entre tipos de logradouro.

### 05 — Incerteza Espacial (ESDA)
Aplica Análise Exploratória de Dados Espaciais: Hexbin Map interativo (Plotly), I de Moran Global (PySAL/esda), LISA clusters significantes (p < 0.05) e mapa interativo Folium com os agrupamentos High-High e Low-Low.

### 06 — Análise Socio-Espacial e Ambiental
Investiga os fatores urbanos que explicam a degradação da acurácia: distância à fronteira municipal (geobr), presença em aglomerados subnormais (geobr), complexidade da malha viária (OSMnx) e adensamento de endereços. Aplica regressão multivariada OLS (statsmodels) com variáveis padronizadas.

---

## Referências

### Modelagem de Incertezas e Geocodificação
- Davis Jr., C. A. (2011). *Avaliação do uso de uma base de referência municipal para auxiliar os processos de geocodificação*.
- Davis Jr., C. A., & Fonseca, F. T. (2007). *Assessing the Certainty of Locations Produced by an Address Geocoding System*. Geoinformatica, 11(1), 103–129.
- Davis Jr., C. A., Fonseca, F. T., & Borges, K. A. V. (2003). *A flexible addressing system for approximate geocoding*.

### Qualidade de Dados Geográficos
- ISO 19157:2013. *Geographic information — Data quality*.
- Guptill, S. C., & Morrison, J. L. (Eds.). (1995). *Elements of Spatial Data Quality*. Elsevier.

### Geocodificação e Acurácia Posicional
- Zandbergen, P. A. (2008). *A comparison of address point, parcel and street geocoding techniques*.
- Goldberg, D. W., Wilson, J. P., & Knoblock, C. A. (2007). *From Text to Geographic Coordinates: The Current State of Geocoding*.

### Record Linkage
- Fellegi, I. P., & Sunter, A. B. (1969). *A Theory for Record Linkage*. JASA.
- Christen, P. (2012). *Data Matching*. Springer.

### Estatística Espacial
- Anselin, L. (1995). *Local Indicators of Spatial Association—LISA*. Geographical Analysis.

### Fontes de Dados
- **IBGE.** (2022). *CNEFE — Cadastro Nacional de Endereços para Fins Estatísticos*.
- **PBH (Prodabel).** (2025). *BHMap Endereços — Geolocalização Oficial Municipal*.

---

## Autor

**Mateus Rezende de Sá Catrinque**
Mestrando em Ciência da Computação — UFMG
[github.com/mcatrinque](https://github.com/mcatrinque)
