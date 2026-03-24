# AVALIAÇÃO DA QUALIDADE DE GEOCODIFICAÇÃO: CNEFE 2022 E A BASE OFICIAL DO MUNICÍPIO DE BELO HORIZONTE

## Introdução
A geocodificação é o processo fundamental de transformação de descrições textuais de localização, como endereços, em coordenadas geográficas precisas. Na análise de políticas públicas e estudos socioespaciais, a qualidade dessa conversão afeta diretamente a validade dos modelos gerados.

Este projeto compõe a pesquisa de dissertação de mestrado em Ciência da Computação pela Universidade Federal de Minas Gerais (UFMG). O trabalho propõe uma avaliação rigorosa e em múltiplas escalas da qualidade posicional, lógica e espacial do Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE), referente ao Censo Demográfico de 2022 do IBGE. Para isso, utiliza-se a base ofical e georreferenciada de endereços e lotes do portal de dados abertos da Prefeitura de Belo Horizonte (BHMap) como _Gold Standard_ (padrão-ouro).

O repositório consolida o pipeline completo de processamento de dados, cruzamento espacial e análise estatística, culminando na geração de métricas de incerteza (GCI, LCI, MCI, PCI) e modelagem espacial para entender como o erro de geocodificação se distribui e a quem ele afeta.

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
Para facilitar a navegabilidade e a experimentação iterativa, o projeto adota a seguinte arquitetura de pastas:

```text
├── data/
│   ├── processed/          # Bases refinadas após matching e enriquecimento
│   └── raw/                # Bases originais do IBGE e BHMap (shapefiles)
├── notebooks/              # Core analítico do projeto
│   ├── 01_ingestao.ipynb
│   ├── 02_matching.ipynb
│   ├── 03_qualidade_logica.ipynb
│   ├── 04_acuracia_incerteza.ipynb
│   ├── 05_segmentacao_tipologica.ipynb
│   ├── 06_analise_socioespacial.ipynb
│   └── 07_sintese_final.ipynb
├── outputs/                # Artefatos gerados pela análise
│   ├── figures/            # Gráficos (PNG, SVG)
│   ├── maps/               # Mapas interativos (HTML)
│   └── tables/             # Tabelas consolidadas (CSV)
├── references/             # Documentação de apoio e planejamento metodológico
├── src/                    # Scripts Python com as funções core da dissertação
│   ├── config.py           # Configuração de caminhos e dicionários base
│   ├── metrics.py          # Implementação LCI, MCI, PCI, GCI e RMSE
│   └── segments.py         # Segmentação estatística (Kruskal-Wallis, etc)
└── README.md
```

## Como Executar
1. Clone este repositório para o seu ambiente local.
2. Certifique-se de que os arquivos do CNEFE 2022 e as bases do BHMap estão devidamente dispostos na pasta `data/raw/`.
3. Crie e ative um ambiente virtual com as dependências necessárias, conforme listado em `requirements.txt`.
4. Execute os *Jupyter Notebooks* situados no diretório `notebooks/` de forma sequencial, iniciando em `01_ingestao.ipynb` para reconstruir integralmente o pipeline.

Em caso de dúvidas sobre a reprodução do ambiente, as versões fixadas dos pacotes Python asseguram a estabilidade da simulação metodológica do estudo de caso.

## Referências
Os algoritmos de métricas de certeza aplicados derivam majoritariamente de adaptações da literatura de Davis Jr. & Fonseca (2007) aplicadas para a escala massiva do IBGE.
- *DAVIS JR, Clodoveu A.; FONSECA, Frederico T.* Certeza na geocodificação de endereços. Em: Anais do VIII Simpósio Brasileiro de Geoinformática (GeoInfo). 2007.

## About
Pesquisa de Dissertação (M.Sc.) em Ciência da Computação (UFMG) explorando incerteza posicional, geocodificação de endereços e desigualdade espacial via Open Data em Belo Horizonte.
