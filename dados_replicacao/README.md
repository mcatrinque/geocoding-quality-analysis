# Dados de replicação

Esta pasta existe por duas razões. A primeira é permitir que o experimento
comparativo do Capítulo 4 — a comparação entre o repositório e o `geocodebr`
contra a mesma verdade de campo — seja refeito por quem clona este repositório,
sem que nenhuma coordenada do cadastro municipal seja redistribuída. A segunda é
que a API consome daqui a tradução entre classe de confiança e erro em metros.

## `nb14_comparativo_medicoes.csv`

Uma linha por endereço da amostra. As colunas guardam **a medição**, não o dado
de origem:

| Coluna | Significado |
|---|---|
| `caso` | Identificador sequencial anônimo |
| `repo_erro_m` | Distância, em metros, entre a resposta do repositório e a verdade de campo |
| `repo_nivel` | Nível de precisão declarado pelo repositório |
| `repo_confianca` | Classe de confiança posicional declarada |
| `repo_identidade` | Incerteza de identidade declarada |
| `repo_gci` | Índice composto empírico |
| `repo_similaridade` | Similaridade do logradouro no casamento |
| `gbr_erro_m` | Distância, em metros, entre a resposta do `geocodebr` e a mesma verdade |
| `gbr_precisao` | Nível de precisão declarado pelo `geocodebr` |

O erro é uma distância entre dois pontos. Ele permite recalcular a tabela de
discriminação (AUC), o cruzamento entre nível e confiança e as tabelas de erro
por estrato — isto é, toda a Seção 7 — mas não permite reconstruir as coordenadas
do BHMap, que continuam fora deste repositório.

## `calibracao_bh.csv`

Derivada do arquivo acima, é a tabela que a API carrega para dizer o que cada
classe significa em metros. Uma linha por combinação de nível de precisão e
classe de confiança, mais linhas de recuo:

| Coluna | Significado |
|---|---|
| `codigo_municipio` | Código IBGE do município em que houve verdade de campo |
| `nivel` | Nível de precisão da resposta; vazio na linha global |
| `confianca` | Classe de confiança posicional; vazio nas linhas de recuo |
| `base` | Granularidade da estimativa: `nivel+confianca`, `nivel` ou `global` |
| `n` | Casos medidos nessa granularidade |
| `erro_mediano_m` | Erro mediano observado |
| `erro_ce90_m` | Erro abaixo do qual estão 90% das respostas |
| `acima_30_pct` | Percentual com erro acima de 30 m |
| `acima_100_pct` | Percentual com erro grosseiro, acima de 100 m |

A API busca do específico para o geral: primeiro o par nível e confiança, depois
o nível, por fim o conjunto. Células com menos de cem casos não entram, porque
não sustentam estimativa de quantil, e a granularidade efetivamente usada vai na
resposta, no campo `base`.

**Esta tabela vale para um município.** O teste de transferibilidade mostrou que
métricas intrínsecas explicam apenas 5,4% da variância do erro mediano entre
setores censitários, de modo que estendê-la a outra cidade seria afirmar o que
não se mediu. A API responde para qualquer município carregado, mas só se declara
calibrada onde existe verdade de campo; nos demais, a resposta sai marcada como
`declarada` e o índice composto é omitido, porque o componente PCI dele foi
calibrado em Belo Horizonte.

Uma limitação a manter em vista: a amostra vem de endereços que existem no
cadastro municipal. A tabela caracteriza o erro das respostas a endereços reais,
não o comportamento do serviço diante de consultas a endereços inexistentes.

## Como os arquivos são gerados

Ambos são escritos pelo notebook `14_api_poc.ipynb` quando ele roda em modo
completo, ou seja, na máquina que tem `scratch/baseline/` com a base do BHMap.
Num clone sem essa base, o mesmo notebook detecta a ausência e recarrega o
arquivo de medições, refazendo a análise a partir dele.

A tabela de calibração é copiada para dentro da imagem Docker da API, de modo
que a resposta do serviço seja reproduzível a partir da imagem, sem depender de
arquivo do hospedeiro.

## Procedência

Verdade de campo derivada do BHMap (Prodabel / Prefeitura de Belo Horizonte).
Respostas do `geocodebr` (IPEA) sobre o CNEFE 2022 (IBGE).
