# AVALIAÇÃO DA QUALIDADE DE GEOCODIFICAÇÃO: CNEFE 2022 E A BASE OFICIAL DO MUNICÍPIO DE BELO HORIZONTE

## Introdução
A geocodificação é o processo fundamental de transformação de descrições textuais de localização, como endereços, em coordenadas geográficas precisas. Na análise de políticas públicas e estudos socioespaciais, a qualidade dessa conversão afeta diretamente a validade dos modelos gerados.

Este projeto compõe a pesquisa de dissertação de mestrado em Ciência da Computação pela Universidade Federal de Minas Gerais (UFMG). O trabalho propõe uma avaliação rigorosa e em múltiplas escalas da qualidade posicional, lógica e espacial do Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE), referente ao Censo Demográfico de 2022 do IBGE. Para isso, utiliza-se a base ofical e georreferenciada de endereços e lotes do portal de dados abertos da Prefeitura de Belo Horizonte (BHMap) como _Gold Standard_ (padrão-ouro).

O repositório consolida o pipeline completo de processamento de dados, cruzamento espacial e análise estatística, culminando na geração de métricas de incerteza (GCI, LCI, MCI, PCI) e modelagem espacial para entender como o erro de geocodificação se distribui e a quem ele afeta. Além da avaliação, o projeto versiona a estrutura que materializa um repositório de endereços de referência: o esquema PostGIS multi-fonte e a API de prova de conceito que devolve a coordenada acompanhada dos seus indicadores de qualidade.

## Objetivos
- **Estimar a Acurácia Posicional**: Medir o erro em metros entre a geocodificação do IBGE e o dado oficial municipal (RMSE, Erro Circular 90%).
- **Mensurar a Incerteza (Certainty Indicators)**: Aplicar e expandir os índices clássicos de avaliação (Positional, Match e Locating Certainty Indicators) para criar um panorama holístico de confiança do dado.
- **Identificar Vieses Geográficos e Sociais**: Descobrir se a qualidade da geocodificação varia de acordo com o valor imobiliário, tipologia construtiva (verticalização) ou proteção social das áreas urbanas (determinismo topográfico e hierarquia viária).

## Metodologia
A pesquisa é estruturada em três estágios essenciais: preparação de dados, cálculo de métricas e análise socioespacial. O fluxo pode ser acompanhado através dos *notebooks* presentes neste repositório.

### Coleta e Preparação de Dados
A extração compreende os endereços do CNEFE 2022 (IBGE) filtrados para o município de Belo Horizonte. A etapa de validação ocorre por meio de junção espacial (spatial join) e métricas de similaridade de strings (Fuzzy Matching) contra a base do BHMap, delimitando os pares-alvo da análise.

### Modelagem de Qualidade (Métricas)
As métricas quantificam a qualidade da correspondência:
- **LCI (Locating Certainty)**: Credibilidade do método de coleta (GPS, estimativa).
- **PCI (Positional Certainty)**: Penalização baseada na verticalização estrutural (identificação de apartamentos).
- **MCI (Match Certainty)**: Confiança da associação baseada na distância euclidiana combinada à similaridade textual.
- **GCI (Geocoding Certainty)**: O índice global derivado das incertezas constituintes.

### Análise Estatística e Espacial
O rigor científico é provido através de métodos que avaliam a não-estacionariedade espacial e os fenômenos globais:
- **Bootstrap Confidence Intervals**: Estimativa robusta do erro populacional.
- **Geographically Weighted Regression (GWR)**: Modelagem da variação local do impacto construtivo no erro.
- **Local Spatial Autocorrelation (LISA)**: Identificação de _hot_ e _cold spots_ espaciais (Getis-Ord Gi*).
- **Random Forest e SHAP**: Avaliação da contribuição independente dos preditores topográficos e socioeconômicos para a geração da incerteza espacial.

## Estrutura do Repositório
O repositório versiona **a análise de qualidade e a estrutura que gera o repositório de endereços**. Dados de entrada, artefatos gerados e o texto da dissertação ficam fora do controle de versão (ver `.gitignore`).

```text
├── notebooks/                     # Núcleo analítico, na ordem de execução
│   ├── 01_ingestao.ipynb
│   ├── 02_matching.ipynb
│   ├── 03_eda_bases.ipynb
│   ├── 04_lci_completude.ipynb
│   ├── 05_acuracia_gci.ipynb
│   ├── 06_consolidacao_edificios.ipynb
│   ├── 07_validacao_gci.ipynb
│   ├── 08_eda_contextual.ipynb
│   ├── 09_segmentacao_tipologica.ipynb
│   ├── 10_segmentacao_uso.ipynb
│   ├── 11_analise_socioespacial.ipynb
│   ├── 12_determinantes_gci.ipynb
│   └── 13_sintese_final.ipynb
├── src/
│   ├── config.py                  # Caminhos, dicionários e parâmetros compartilhados
│   ├── metrics.py                 # Implementação de LCI, MCI, PCI, CDI, GCI, RMSE e CE90
│   ├── normalize.py               # Forma canônica de logradouros (abreviações, acentos)
│   ├── env.py                     # Credenciais do banco lidas do ambiente (.env)
│   ├── db/
│   │   └── init.sql               # Esquema PostGIS: fonte, endereco e unidade
│   └── api/                       # Prova de conceito do serviço (FastAPI)
│       ├── main.py                # Rotas /geocode, /reverse e /usage
│       ├── database.py            # Sessão SQLAlchemy
│       └── schemas.py             # Contratos de entrada e saída
├── scripts/
│   ├── load_cnefe_to_postgis.py   # Carga do parquet consolidado no PostGIS
│   ├── enrich_master_metrics.py   # Enriquecimento da base mestra de métricas
│   └── process_context_layers.py  # Preparo das camadas de contexto urbano
├── docker-compose.yml             # PostGIS + API
├── run_pipeline.py                # Execução encadeada dos notebooks
├── requirements.txt
├── .env.example                   # Modelo das credenciais locais
└── README.md
```

Ficam fora do versionamento, por serem dados externos, artefatos reprodutíveis ou material da dissertação: `data/` (CNEFE 2022 e bases do BHMap), `outputs/` (figuras, mapas e tabelas), `references/` (bibliografia) e `docs/` (texto e relatórios).

## Como Executar

### Análise
1. Clone o repositório e crie um ambiente virtual com as dependências de `requirements.txt`.
2. Disponha os arquivos do CNEFE 2022 e as bases do BHMap em `data/raw/`.
3. Execute os *notebooks* de `notebooks/` em sequência, a partir de `01_ingestao.ipynb`, ou use `run_pipeline.py` para encadeá-los.

As versões fixadas dos pacotes asseguram a estabilidade da reprodução. A extensão espacial do DuckDB é instalada em tempo de execução, conforme a nota em `requirements.txt`.

### Repositório de endereços e API
O repositório de referência é um PostGIS com o esquema de `src/db/init.sql`, servido por uma API FastAPI que devolve, junto da coordenada, os indicadores de qualidade calculados na análise.

1. Copie `.env.example` para `.env` e defina as credenciais. O `.env` não é versionado; nenhuma senha fica no código.
2. Suba os serviços: `docker compose up -d`. O `init.sql` cria as extensões (PostGIS e `pg_trgm`), as tabelas e os índices na primeira execução.
3. Carregue os endereços consolidados pela análise: `python scripts/load_cnefe_to_postgis.py`.
4. Consulte a documentação interativa em `http://localhost:8000/docs`.

O modelo separa o endereço geocodificável (logradouro, número e coordenada) das unidades que compartilham a mesma coordenada, de modo que um edifício vertical ocupe um ponto e não uma unidade por apartamento. As respostas trazem a fonte, o *Plus Code* da coordenada, os indicadores (LCI, MCI, CDI e GCI empírico) e a classe de confiança derivada deles.

## Referências
Os indicadores de certeza aplicados derivam de adaptações da literatura de Davis Jr. & Fonseca (2007), levadas à escala do CNEFE.
- DAVIS JR., Clodoveu A.; FONSECA, Frederico T. Assessing the certainty of locations produced by an address geocoding system. *GeoInformatica*, v. 11, n. 1, p. 103–129, 2007.
- MARTINS, D.; DAVIS JR., Clodoveu A.; FONSECA, Frederico T. Geocodificação de endereços urbanos com indicação de qualidade. In: *Anais do XIII Simpósio Brasileiro de Geoinformática (GeoInfo)*, 2012.
- DAVIS JR., Clodoveu A.; ALENCAR, Rafael Odon de. Evaluation of the quality of an online geocoding resource in the context of a large Brazilian city. *Transactions in GIS*, v. 15, n. 6, p. 851–868, 2011.

## About
Pesquisa de Dissertação (M.Sc.) em Ciência da Computação (UFMG) explorando incerteza posicional, geocodificação de endereços e desigualdade espacial via Open Data em Belo Horizonte.
