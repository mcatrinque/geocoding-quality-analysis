<div align="center">
  <h1>Análise de Qualidade e Incerteza de Dados Geoespaciais</h1>
  <h3>Estudo Empírico do CNEFE 2022 frente ao BHMap Endereços</h3>
  <p><i>Repositório Oficial da Dissertação de Mestrado (Ciência da Computação - UFMG)</i></p>
</div>

---

## Visão Geral do Projeto

Este projeto avalia empiricamente a qualidade e a incerteza de dados de geocodificação no **Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE 2022)** do IBGE, utilizando a base municipal **BHMap Endereços** (Belo Horizonte - MG) como *Gold Standard*. 

A dissertação segue um desenho metodológico inspirado no estudo clássico de Davis (2011). O foco central é conduzir uma **avaliação empírica, metodológica e rigorosamente reprodutível** sobre a acurácia posicional, a consistência e a incompletude do cadastro federal, modelando a incerteza espacial por meio das métricas PCI, MCI, LCI e GCI (Davis & Fonseca, 2007).

### Objetivos Principais
1. **Medir a Completude e Consistência:** Quantificar lacunas, duplicações e coerência dos dados do CNEFE 2022 em relação ao BHMap.
2. **Mensurar Acurácia Posicional:** Calcular o erro posicional médio e absoluto (RMSE, $e_i$, Misallocation) dos pares conjugados.
3. **Modelar Incertezas (MCI/PCI/LCI/GCI):** Empregar o modelo formal para auditar as taxas de correspondência híbrida (Espacial + Fuzzy String Matching).
4. **Analisar o Viés Espacial:** Testar estatisticamente se a completude, o erro e a incerteza variam devido à heterogeneidade urbana (territórios vulneráveis vs. não vulneráveis; uso comercial vs. residencial).

---

## Arquitetura da Dissertação

O escopo do texto acadêmico e a geração das evidências via código convergem para os seguintes pilares teóricos:

1. **Introdução:** Motiva a relevância dos cadastros de endereços para políticas públicas e análises espaciais, delimitando as perguntas de pesquisa sobre heterogeneidade intraurbana.
2. **Base Conceitual e Trabalhos Relacionados:** Fundamentado na normativa ISO 19157 (Qualidade de Dados Geográficos) e na modelagem de Davis & Fonseca (2007). Explora o impacto de vícios espaciais e fontes de incerteza em Sistemas de Informação Geográfica (GIS).
3. **Dados e Área de Estudo:** Contextualiza a heterogeneidade socioespacial de Belo Horizonte. Trata do pré-processamento, transformação de Datum (CRS SIRGAS 2000 / UTM 23S) e limpeza vetorial nativa dos arquivos massivos.
4. **Metodologia (O Pipeline):** Protocolo 100% reprodutível delineando desde o vínculo probabilístico (Levenshtein Token Sort Ratio via RapidFuzz) e bloqueio geográfico via R-Tree (buffer de 50 metros), até os limites matemáticos dos Indicadores de Certeza e testes estatísticos de hipóteses (Bootstrap, autocorrelação espacial).
5. **Resultados e Discussão:** Sintetiza padrões espaciais extraídos dos *Heatmaps KDE* mostrando exatamente "onde" estão as maiores fragilidades de endereçamento urbano, apontando limitações do CNEFE frente a gargalos do próprio linkage.

---

## Estrutura do Repositório 

O projeto segue um formato modular otimizado para a reprodutibilidade:

*   **`data/`**: Diretório principal de persistência:
    *   `raw/`: Dados massivos (ex: CNEFE e BHMap).
    *   `processed/`: Arquivos canônicos hiperformáticos serializados em `.parquet`.
*   **`notebooks/`**: A camada de apresentação que rodam o fluxo lógico, desde o ETL até os cálculos geoespaciais e relatórios visuais.
*   **`src/`**: Pilar de engenharia do projeto, consumido pelos Notebooks:
    *   `etl_pipeline.py`: Integração *Out-of-Core* em C++ via DuckDB.
    *   `matching.py`: Motor de Distância Espacial e Distância de Edição (Levenshtein).
    *   `metrics.py`: Ferramentais puros de modelagem linear e estatística (RMSE, Completude, MCI).
    *   `maps.py`: Wrapper para rederizações cartográficas.
*   **`outputs/`**: Entregáveis contendo os resultados e análise do projeto.

---

## Como Executar o Projeto

Todo o orquestramento do pipeline geográfico é encapsulado via **Invoke**. 

### 1. Bootstrapping
Crie o ambiente virtual nativo e instale as dependências.
**Windows:**
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
invoke setup
```
**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
invoke setup
```
*O comando `invoke setup` audita a máquina.*

### 2. O Pipeline Invoke
Dentro do ambiente, é possível acionar os estágios vitais da pesquisa via terminal:

*   **`invoke clean`**:  Apaga qualquer resíduo temporal e outputs gráficos gerados no projeto.
*   **`invoke etl`**: *Extract, Transform and Load*. Inicializa o DuckDB; processa o JSON e os shapefiles brutos; normaliza os logradouros nativamente, e escreve `.parquets` contendo registros de endereço do município de Belo Horizonte.
*   **`invoke match`**: Inicia o Motor Híbrido, ligando pontualmente Endereço a Endereço baseando-se por aproximação esférica (GeoPandas) combinada de análise descritiva de strings (RapidFuzz).
*   **`invoke analyze`**: Calcula o RMSE, modela o MCI e exporta imagens para o capítulo de resultados.
*   **`invoke all`**: Executa o pipeline completo para reproduzir todos os dados da dissertação.

---

## Referências Fundamentais

Esta pesquisa é ancorada na literatura científica clássica e contemporânea voltada para Qualidade de Geoinformação (GI) e métodos quantitativos iterativos em Computação.

**Modelagem de Incertezas e Avaliação de Endereçamento:**
*   Davis Jr., C. A. (2011). *Avaliação do uso de uma base de referência municipal para auxiliar os processos de geocodificação*. 
*   Davis Jr., C. A., & Fonseca, F. T. (2007). *Assessing the Certainty of Locations Produced by an Address Geocoding System*. Geoinformatica, 11(1), 103-129. (PCI, MCI, LCI e GCI).
*   Davis Jr., C. A., Fonseca, F. T., & Borges, K. A. V. (2003). *A flexible addressing system for approximate geocoding*. 

**Padrões de Qualidade ISO e Erros Espaciais:**
*   ISO 19157:2013. *Geographic information — Data quality*. 
*   Guptill, S. C., & Morrison, J. L. (Eds.). (1995). *Elements of Spatial Data Quality*. Elsevier.
*   Goodchild, M. F. et al. (Várias Obras). *Fundamentação ampla sobre Incerteza/qualidade em SIG*.

**Técnicas Acurácia e Geocodificação Comercial:**
*   Zandbergen, P. A. (2008). *A comparison of address point, parcel and street geocoding techniques*. Computers, Environment and Urban Systems.
*   Ratcliffe, J. H. (2001). *On the accuracy of TIGER-type geocoded address data in relation to cadastral and census areal units*. 
*   Goldberg, D. W., Wilson, J. P., & Knoblock, C. A. (2007). *From Text to Geographic Coordinates: The Current State of Geocoding*. 

**Record Linkage Estrutural:**
*   Fellegi, I. P., & Sunter, A. B. (1969). *A Theory for Record Linkage*. Journal of the American Statistical Association.
*   Jaro, M. A. (1989). *Advances in Record-Linkage Methodology as Applied to Matching the 1985 Census of Tampa, Florida*.
*   Christen, P. (2012). *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*. Springer.

**Estatística Robusta (Amostras Espaciais):**
*   Efron, B., & Tibshirani, R. J. (1994). *An Introduction to the Bootstrap*. CRC press.
*   Anselin, L. (1995). *Local Indicators of Spatial Association—LISA*. Geographical Analysis.

**Fontes Oficiais Analisadas:**
*   **IBGE.** (2022). *Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE) - Documentação Técnica e Dicionário de Variáveis*. 
*   **PBH (Prodabel).** (2025). *Documentação/Metadados BHMap Endereços (Geolocalização Oficial Municipal)*. Belo Horizonte.
