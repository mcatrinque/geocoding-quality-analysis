# Repositório de endereços de referência para geocodificação: formação e avaliação com o CNEFE 2022 em Belo Horizonte

Dissertação de Mateus Rezende de Sá Catrinque, PPGCC/DCC/UFMG, orientada pelo Prof. Dr. Clodoveu Augusto Davis Jr. O objeto é a formação de um repositório de endereços de referência. A comparação CNEFE × BHMap é seu pilar empírico e a API é uma prova de conceito.

## Estado em 01/10/2026

A auditoria identificou associação incorreta entre métricas e registros depois da ordenação do pareamento. A junção foi corrigida por `idx_cnefe_original`, e NB03 a NB05 reproduziram o mestre-base reparado. Em 01/10, o enriquecimento contextual preservou 1.172.902 registros e produziu um mestre com 119 colunas. O arquivo promovido em `data/processed/` tem SHA-256 `536aba45d07b1a974d37eb69c1cf994e1c03781062512860d7a5690d13f0441d`. NB06, NB08, NB09, NB12 e NB13 foram executados em isolamento sobre essa versão. A suíte passou com 136 testes, sem falhas ou testes ignorados, incluindo PostGIS real com dados sintéticos. A carga censal completa e os contratos HTTP na imagem Docker foram verificados. A dissertação continua em revisão.

O [estado de 01/10](docs/reparos/2026-10-01/estado_dos_reparos.md) distingue os resultados reexecutados das verificações ainda pendentes. O [relatório de 30/09](docs/reparos/2026-09-30/estado_dos_reparos.md) e o [parecer de auditoria](docs/auditorias/2026-09-25/parecer.md) preservam o histórico. Esses documentos são locais, excluídos do Git pela configuração atual.

Não estão sustentadas as afirmações anteriores de ortogonalidade dos indicadores ou de transferência refutada entre cidades. O GCI com MCI depende do cadastro de comparação. O inverso do CDI é um escore experimental, não uma probabilidade calibrada de identidade correta.

## Protocolos e unidades

| Protocolo | O que observa | Limitação |
| --- | --- | --- |
| Proximidade, raio de 100 m | Existência de ponto BHMap perto do registro CNEFE | Não confirma endereço e trunca a distância |
| Chave textual conciliada, sem raio | Logradouro normalizado e primeira sequência numérica coincidentes | Descarta sufixo e escolhe o mais próximo entre candidatos da chave |
| Sensibilidade com sufixo | Conjuntos preservando um sufixo alfabético | Altera a unidade de correspondência e requer revisão manual |

Pela regra conciliada, 913.534 dos 1.180.102 registros encontram chave comum, com mediana de deslocamento de 9,72 m, CE90 de 33,59 m e 2,63% acima de 100 m. São discrepâncias entre fontes, não erros absolutos certificados. Contam-se 346.244 chaves comuns, 109.763 só no CNEFE e 76.723 só no BHMap. Esses conjuntos não são uma matriz de confusão sem rótulos independentes de verdade.

## Métricas

| Indicador | Interpretação e dependência |
| --- | --- |
| CDI | Contagem de registros com coordenadas compartilhadas após arredondamento |
| CCR | Contenção no setor declarado, exige malha auxiliar |
| DRS | Distância à via, exige camada viária |
| LCI local | Pesos heurísticos sobre `NV_GEO_COORD`, sem calibração métrica demonstrada |
| MCI local | Similaridade e proximidade ao BHMap, depende de referência externa |
| `PCI_empirico` legado | `1/CDI`. Não equivale ao Parsing Certainty Indicator de Davis e Fonseca |
| `GCI_empirico` legado | `LCI × MCI / CDI`, composto experimental e extrínseco |
| Mediana, CE90 e cauda | Resumo do deslocamento sob protocolo e população declarados |

O dicionário de `NV_GEO_COORD` distingue coordenada original, modificada por agrupamento de apartamentos, estimada por ausência ou invalidade, face de quadra, localidade e setor. O código 2 não significa simplesmente estimativa próxima.

## Pipeline analítico

O [run_pipeline.py](run_pipeline.py) prepara as camadas de contexto, executa os notebooks de análise em sequência e roda o enriquecimento contextual entre o NB05 e o NB06. `--from etl --dry-run` mostra a retomada sem executar nem limpar arquivos. `--com-api` inclui os notebooks que exigem a API no ar (NB14 e NB17).

Cada notebook narra uma etapa da análise: introdução com as perguntas, as entradas e as saídas, seções com contexto, código e interpretação dos resultados, e conclusão com o próximo passo.

| Notebook | Conteúdo |
| --- | --- |
| [01](notebooks/01_ingestao.ipynb) | Ingestão do CNEFE e do BHMap, projeção e composição das bases |
| [02](notebooks/02_matching.ipynb) | Proximidade e pareamento pela chave de logradouro e número, conciliação de grafia e sensibilidade |
| [03](notebooks/03_eda_bases.ipynb) | Exploração das bases e métricas intrínsecas da coordenada (CDI, CCR, DRS, CSI) |
| [04](notebooks/04_lci_completude.ipynb) | Indicador de localização e completude do endereço |
| [05](notebooks/05_acuracia_gci.ipynb) | Deslocamento entre os cadastros, compostos locais, H1 e H2 |
| [06](notebooks/06_consolidacao_edificios.ipynb) | Agrupamento de registros por endereço e coordenada |
| [07](notebooks/07_validacao_gci.ipynb) | Indicadores de qualidade e deslocamento (H7) |
| [08](notebooks/08_eda_contextual.ipynb) | Camadas de contexto urbano e deslocamento por regional |
| [09](notebooks/09_segmentacao_tipologica.ipynb) | Tipologia, coleta e contexto com inferência por chave e blocos espaciais |
| [10](notebooks/10_segmentacao_uso.ipynb) | Atividade econômica e vilas e favelas |
| [11](notebooks/11_analise_socioespacial.ipynb) | Dependência espacial do deslocamento (H3) |
| [12](notebooks/12_determinantes_gci.ipynb) | Predição do deslocamento em blocos espaciais |
| [14](notebooks/14_api_poc.ipynb) | Prova de conceito da API e comparação com o geocodebr |
| [15](notebooks/15_conjuntos_estratos.ipynb) | Conjuntos de chaves, estratos e vetores de deslocamento |
| [16](notebooks/16_adjudicacao_cadastral.ipynb) | Evidência cadastral da cauda e dos registros sem par |
| [17](notebooks/17_teste_operacional_independente.ipynb) | Teste independente da calibração da API |
| [18](notebooks/18_restricao_territorial.ipynb) | Concordância de bairro e CEP e restrição territorial do pareamento |
| [22](notebooks/22_conjuntos_exclusivos.ipynb) | Composição das chaves exclusivas e filtro de existência |
| [23](notebooks/23_referencia_municipal_completa.ipynb) | Pareamento com todos os pontos do cadastro municipal, atributos de placa e situação como sensibilidade |
| [24](notebooks/24_composicao_bases.ipynb) | Como cada base representa endereços e estratos, e quem está em cada conjunto |
| [25](notebooks/25_setor_censitario.ipynb) | Setor censitário dos pares, restrição por setor e dependência espacial do deslocamento |

A numeração ainda tem lacunas e será refeita em sequência contínua.

O enriquecimento contextual atribui atributos apenas quando os candidatos espaciais concordam, e calcula presença geométrica de risco e vila ou favela separadamente dos rótulos. Empates de vias e sobreposições ficam documentados no manifesto. A atividade econômica a até 50 m indica proximidade, não identidade do estabelecimento. O NB08 separa cobertura do atributo, presença espacial e deslocamento por identidade.

## Repositório e API

O [esquema PostGIS](src/db/init.sql) separa fonte, endereço, unidade, registro de origem e manifesto da carga. O manifesto registra hashes e contagens. Complementos ficam fora da chave geocodificável. `n_unidades` é um nome legado para registros agrupados, sem comprovação de unidades distintas.

A [carga](scripts/load_cnefe_to_postgis.py) usa o CNEFE completo, sem excluir registros por ausência de vizinho municipal. Métricas são opcionais e anexadas pelo índice original. A substituição é delimitada por fonte, município e versão em uma transação. Testes com registros sintéticos em PostGIS real verificaram preservação de IDs de endereços e unidades, origens, outro município e rollback após falha intermediária. Uma primeira tentativa censal encontrou incompatibilidade no tipo inteiro do CDI, corrigida antes da nova execução. A execução corrigida persistiu 1.180.102 origens, 590.615 endereços, 690.016 complementos e 12.638 logradouros de busca em 8,40 minutos. A recarga censal ainda não foi medida.

A consolidação usa componentes conexos da mesma chave ligados por passos de até 30 m. Isso não limita o diâmetro do grupo a 30 m. A dispersão é a diagonal da caixa envolvente. Indicadores discordantes no grupo ficam ausentes no agregado e são preservados por registro de origem. O número preserva sufixo: `10` e `10A` não recebem correspondência exata entre si.

| Rota | Contrato |
| --- | --- |
| `GET/POST /geocode` | Candidatos ordenados, fonte, coordenada, Plus Code e nível de correspondência |
| `POST /reverse` | Candidato mais próximo em metros, nível `proximidade`, sem comprovação de identidade |
| `GET /cobertura` | Conteúdo carregado por município e fonte |
| `GET /health` | Estado do banco, sem detalhes internos de erro |
| `GET /usage` | Eventos persistidos e perdas e pendências do processo |

As classes de qualidade são heurísticas. A tabela histórica de BH foi usada no desenvolvimento e não habilita `calibrada`. O validador exige amostra independente, versões compatíveis, métricas válidas e contagens consistentes. A versão da resposta é vinculada ao manifesto efetivo da carga. Falta produzir uma avaliação independente elegível. As rotas permanecem `declarada`, sem estimativas em metros nem GCI apresentado como calibrado. Uma variável de ambiente não certifica o conteúdo do banco.

A contabilização passa por fila em memória e pode perder eventos. Perdas, pendências e limite de requisições são por processo. Com múltiplos workers, o limite não é uma cota global por cliente.

O esquema permite registrar outras fontes, mas a integração operacional de BHMap e a consolidação entre fontes não estão demonstradas. O ponto de extensão para modelos de linguagem não implementa crowdsourcing nem atualização do cadastro.

## Execução

1. Prepare Python com `requirements.txt` e as fontes em `data/raw/`. Versões fixadas ajudam, mas não garantem equivalência entre sistemas.
2. Inspecione `python run_pipeline.py --from etl --dry-run` antes de regenerar análises. Executar células não resolve automaticamente as revisões científicas pendentes.
3. Para a API, copie `.env.example` para `.env` e configure credenciais locais.
4. Inicie `docker compose up -d --build`. Execute `python scripts/load_cnefe_to_postgis.py --parquet <fonte-completa.parquet> --municipio "Belo Horizonte" --uf MG --codigo-ibge 3106200 --versao-fonte 2022`. Use `--qualidade-parquet` somente com métricas da mesma origem e versão.
5. Consulte `http://localhost:8000/docs` e execute `python -m pytest tests/`. Os testes de integração exigem o PostGIS de teste configurado.

`API_KEYS` ativa identificação e `LIMITE_POR_MINUTO` define o limite por processo. O acesso é aberto por padrão. Em 01/10/2026, a suíte passou contra PostGIS isolado com dados sintéticos de dois municípios. A imagem em `localhost:58001` foi verificada com a carga completa pelas rotas de saúde, cobertura, geocodificação, reversa e uso. Confirmaram-se Plus Code, versão vinculada ao manifesto, recusa em município não carregado e qualidade declarada. Essa verificação operacional não substitui a avaliação independente de acurácia, ainda pendente.

## Dados locais e referências

`data/`, `outputs/`, `references/`, `docs/` e `scratch/` contêm fontes, análises, bibliografia e material local. A amostra de revisão contém endereços e não foi publicada. Um pacote público reproduzível exige seleção de artefatos e revisão das licenças.

Referências de base: Davis Jr. e Fonseca, *Assessing the certainty of locations produced by an address geocoding system* (GeoInformatica, 2007); Davis Jr. e Alencar, *Evaluation of the quality of an online geocoding resource in the context of a large Brazilian city* (Transactions in GIS, 2011); documentação do IBGE para o CNEFE e as coordenadas do Censo 2022. A conferência bibliográfica está registrada na auditoria local.
