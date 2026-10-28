# Repositório de endereços de referência do CNEFE 2022 e protocolo de avaliação de posição, cobertura e informação de qualidade

Trabalho de mestrado de Mateus Rezende de Sá Catrinque no PPGCC/DCC/UFMG, orientado pelo Prof. Dr. Clodoveu Augusto Davis Jr.

Este repositório reúne três partes:

1. Um repositório de endereços de referência para geocodificação, com esquema PostGIS e carga do CNEFE 2022 do IBGE parametrizada por município.
2. Um protocolo que compara o CNEFE com um cadastro municipal de endereços quanto à posição, à cobertura e à informação de qualidade de cada coordenada.
3. Uma API, como prova de conceito, que consulta o repositório e devolve cada coordenada com o nível de precisão do casamento e a qualidade declarada.

Belo Horizonte é o caso de teste, e o cadastro de comparação é o BHMap, da Prefeitura. O esquema, a carga, o protocolo e o contrato da API não dependem da cidade. Os números, sim, valem só para Belo Horizonte. Aplicar o protocolo a outro município exige um cadastro municipal com logradouro, número e coordenada. Sem esse cadastro restam os indicadores intrínsecos, que não medem a posição.

## Protocolo de pareamento

| Protocolo | O que observa | Limitação |
| --- | --- | --- |
| Proximidade, raio de 100 m | Se existe ponto do BHMap perto do registro do CNEFE | Não confirma que o ponto é o mesmo endereço, escolhe o mais próximo e descarta o que passa do raio |
| Chave de logradouro e número | Logradouro canônico e primeira sequência numérica coincidentes, com conciliação de grafia e sem limite de distância | Mede discrepância entre os cadastros, e não erro de campo. Entre vários pontos da mesma chave, escolhe o mais próximo |

Os resultados de deslocamento usam a chave. A proximidade aparece só como diagnóstico de vizinhança e para mostrar o efeito do protocolo. A conciliação de grafia (`conciliar_logradouros`, em [src/metrics.py](src/metrics.py)) une variações como TEREZA e TERESA ou BEC e BECO e exige margem sobre o segundo candidato, para não unir logradouros distintos de nome parecido, seguindo Davis Jr. e de Salles (2007).

## Resultado principal

O [NB23](notebooks/23_referencia_municipal_completa.ipynb) compara os 1.180.102 registros do CNEFE com os 757.113 pontos do BHMap. Pela chave, 1.062.044 registros encontram par, 90,0% do CNEFE. A mediana do deslocamento é de 9,84 m e o P90 de 35,59 m. Ficam a mais de 100 m 29.775 pares, 2,80% dos pareados. Há 51.226 chaves exclusivas do CNEFE e 208.967 do BHMap.

Essas distâncias são discrepâncias entre duas fontes, e não erros certificados em campo. A ausência de uma chave numa das bases não prova que o imóvel não existe.

## Indicadores

| Indicador | Interpretação e dependência |
| --- | --- |
| CDI | Número de registros que compartilham a mesma coordenada após arredondamento |
| CCR | Se o ponto cai no setor censitário declarado, na malha preliminar do Censo 2022 |
| DRS | Distância à via mais próxima, exige camada viária |
| CSI | Distância ao centroide do setor censitário |
| LCI local | Pesos atribuídos aos níveis de `NV_GEO_COORD`, sem calibração contra o erro |
| MCI local | Similaridade e proximidade ao BHMap, depende do cadastro externo |
| `PCI_empirico` | `1/CDI`, multiplicidade inversa. Não equivale ao Parsing Certainty Indicator de Davis Jr. e Fonseca (2007) |
| `GCI_empirico` | `LCI × MCI / CDI`, composto experimental que depende do cadastro externo |
| Mediana, P90 e cauda | Resumo do deslocamento sob protocolo e população declarados |

O dicionário de `NV_GEO_COORD` distingue coordenada original, modificada pelo agrupamento de apartamentos, estimada por ausência ou invalidade da original, face de quadra, localidade e setor. O código 2 não significa estimativa próxima.

## Notebooks

Cada notebook abre com as perguntas, as entradas e as saídas, e interpreta os resultados ao lado do código.

| Notebook | Conteúdo |
| --- | --- |
| [01](notebooks/01_ingestao.ipynb) | Ingestão do CNEFE e do BHMap, projeção e composição das bases |
| [02](notebooks/02_matching.ipynb) | Proximidade, pareamento pela chave, conciliação de grafia e sensibilidade ao limiar |
| [03](notebooks/03_eda_bases.ipynb) | Exploração das bases e métricas intrínsecas da coordenada (CDI, CCR, DRS, CSI) |
| [04](notebooks/04_lci_completude.ipynb) | Indicador de localização e completude do endereço |
| [05](notebooks/05_acuracia_gci.ipynb) | Deslocamento entre os cadastros e compostos locais de qualidade |
| [06](notebooks/06_consolidacao_edificios.ipynb) | Agrupamento de registros por endereço e coordenada |
| [07](notebooks/07_validacao_gci.ipynb) | Quanto os indicadores de qualidade acompanham o deslocamento |
| [08](notebooks/08_eda_contextual.ipynb) | Camadas de contexto urbano e deslocamento por regional |
| [09](notebooks/09_segmentacao_tipologica.ipynb) | Tipo de domicílio, nível de coleta, vilas e favelas, hierarquia viária e declividade |
| [10](notebooks/10_segmentacao_uso.ipynb) | Atividade econômica e pareamento dentro e fora das vilas e favelas |
| [11](notebooks/11_analise_socioespacial.ipynb) | Dependência espacial do deslocamento por setor censitário |
| [12](notebooks/12_determinantes_gci.ipynb) | Predição do deslocamento em blocos espaciais |
| [14](notebooks/14_api_poc.ipynb) | Prova de conceito da API e comparação com o geocodebr |
| [15](notebooks/15_conjuntos_estratos.ipynb) | Conjuntos de chaves, estratos e vetores de deslocamento |
| [16](notebooks/16_adjudicacao_cadastral.ipynb) | Evidência do cadastro imobiliário para os pares distantes e os registros sem par |
| [17](notebooks/17_teste_operacional_independente.ipynb) | Teste independente da calibração da API |
| [18](notebooks/18_restricao_territorial.ipynb) | Concordância de bairro e CEP e restrição territorial do pareamento |
| [22](notebooks/22_conjuntos_exclusivos.ipynb) | Composição das chaves exclusivas de cada base |
| [23](notebooks/23_referencia_municipal_completa.ipynb) | Pareamento com todos os pontos do cadastro municipal |
| [24](notebooks/24_composicao_bases.ipynb) | Como cada base representa endereços e estratos |
| [25](notebooks/25_setor_censitario.ipynb) | Setor censitário dos pares e dependência espacial do deslocamento |
| [26](notebooks/26_verificacoes_robustez.ipynb) | Robustez do pareamento, do setor e da dependência espacial |
| [27](notebooks/27_verificacoes_revisao_artigo.ipynb) | Sensibilidades adicionais dos contrastes e da conciliação |

Os NB06 a NB12 usam os 1.177.753 registros que têm algum ponto do BHMap a até 100 m. Os 2.349 registros fora desse universo são 0,2% do CNEFE. A numeração tem lacunas e será refeita em sequência contínua.

## Pipeline

O [run_pipeline.py](run_pipeline.py) prepara as camadas de contexto, executa os notebooks em sequência e roda o enriquecimento contextual entre o NB05 e o NB06. A opção `--from` retoma a partir de uma etapa, e `--dry-run` mostra o plano sem executar nem apagar arquivos. Com `--com-api`, entram também o NB14 e o NB17, que exigem a API no ar. O NB27 roda à parte.

O enriquecimento contextual só atribui um atributo quando os candidatos espaciais concordam, e calcula a presença geométrica em área de risco e em vila ou favela separadamente dos rótulos. A atividade econômica a até 50 m indica proximidade, e não que se trata do mesmo estabelecimento.

## Repositório e API

O [esquema PostGIS](src/db/init.sql) separa fonte, endereço, unidade, registro de origem e manifesto da carga. O manifesto registra hashes e contagens. Complementos ficam fora da chave geocodificável. `n_unidades` conta registros agrupados, sem comprovar unidades distintas.

A [carga](scripts/load_cnefe_to_postgis.py) usa o CNEFE completo e não exclui registros por falta de vizinho no cadastro municipal. A substituição é feita por fonte, município e versão, numa única transação, e a recarga da mesma versão é idempotente. Em Belo Horizonte, a carga gravou 1.180.102 registros de origem, 590.615 endereços, 690.016 complementos e 12.638 logradouros de busca.

A consolidação liga registros da mesma chave por passos de até 30 m. Isso não limita o diâmetro do grupo a 30 m. A dispersão é a diagonal da caixa envolvente. O número preserva sufixo, então `10` e `10A` não recebem correspondência exata entre si.

| Rota | Contrato |
| --- | --- |
| `GET/POST /geocode` | Candidatos ordenados, fonte, coordenada, Plus Code, nível de precisão e qualidade |
| `POST /reverse` | Candidato mais próximo em metros, nível `proximidade`, sem comprovar identidade |
| `GET /cobertura` | Conteúdo carregado por município e fonte |
| `GET /health` | Estado do banco, sem detalhes internos de erro |
| `GET /usage` | Eventos registrados, perdas e pendências do processo |

A qualidade da resposta tem duas dimensões separadas. A confiança posicional depende do nível de precisão do casamento. A incerteza de identidade depende de quantos registros compartilham a coordenada (CDI). As duas classes são heurísticas e vêm com o motivo em texto.

O campo `calibracao` diz o que a classe significa em metros quando isso foi medido. A tabela [dados_replicacao/calibracao_bh.csv](dados_replicacao/calibracao_bh.csv) vem do teste independente do NB17, numa amostra separada por blocos espaciais. A API marca a resposta como `calibrada` só quando o município, a versão dos dados carregados e a versão da política de resposta coincidem com as do teste. Nos demais casos, a qualidade sai como `declarada`, sem estimativa em metros. A tabela usada durante o desenvolvimento da política (`calibracao_bh_desenvolvimento_20260911.csv`) não habilita `calibrada`.

A contabilização de uso passa por fila em memória e pode perder eventos. O limite de requisições vale por processo, e não como cota global por cliente quando há vários workers.

O esquema permite registrar outras fontes, mas a integração operacional do BHMap e a consolidação entre fontes ainda não foram demonstradas. O ponto de extensão para tratar o endereço de entrada com modelos de linguagem ([src/api/enriquecimento.py](src/api/enriquecimento.py)) está previsto, sem implementação de crowdsourcing nem de atualização do cadastro.

## Execução

1. Instale as dependências de `requirements.txt` e coloque as fontes em `data/raw/`.
2. Confira o plano com `python run_pipeline.py --from etl --dry-run` antes de regenerar as análises.
3. Para a API, copie `.env.example` para `.env` e configure as credenciais locais.
4. Suba os serviços com `docker compose up -d --build` e carregue o CNEFE:
   `python scripts/load_cnefe_to_postgis.py --parquet <fonte.parquet> --municipio "Belo Horizonte" --uf MG --codigo-ibge 3106200 --versao-fonte 2022`.
   Use `--qualidade-parquet` só com métricas da mesma origem e versão.
5. A documentação interativa fica em `http://localhost:8000/docs`. Os testes rodam com `python -m pytest tests/`, e os de integração exigem um PostGIS de teste configurado.

`API_KEYS` ativa a identificação de clientes e `LIMITE_POR_MINUTO` define o limite por processo. Sem essas variáveis, o acesso é aberto.

## Dados

As bases de origem não estão neste repositório. O CNEFE 2022 é publicado pelo IBGE. O BHMap e as camadas municipais são da Prefeitura de Belo Horizonte (Prodabel). A pasta [dados_replicacao/](dados_replicacao/) guarda as medições anonimizadas da comparação com o geocodebr e a tabela de calibração da API, sem redistribuir coordenadas do cadastro municipal.

## Referências

- Davis Jr., C. A. e Fonseca, F. T. Assessing the certainty of locations produced by an address geocoding system. *GeoInformatica*, 11(1), p. 103-129, 2007.
- Davis Jr., C. A. e de Salles, E. Approximate string matching for geographic names and personal names. *IX Simpósio Brasileiro de Geoinformática (GEOINFO)*, p. 49-60, 2007.
- Davis Jr., C. A. e de Alencar, R. O. Evaluation of the quality of an online geocoding resource in the context of a large Brazilian city. *Transactions in GIS*, 15(6), p. 851-868, 2011.
- IBGE. Documentação do Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE) e das coordenadas do Censo 2022.
