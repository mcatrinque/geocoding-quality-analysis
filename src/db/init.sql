-- Esquema do repositório de endereços de referência.
-- O arquivo é idempotente: roda na inicialização do container (via
-- docker-entrypoint-initdb.d) e também pode ser reaplicado sobre um banco já
-- existente pelo script de carga, sem perder dados.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tabela Fonte: mapeia as diferentes origens dos dados (ex: CNEFE, BHMap).
-- O esquema é multi-fonte por construção: novas bases entram sem alterar o modelo.
CREATE TABLE IF NOT EXISTS fonte (
    id_fonte SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fonte_nome ON fonte(nome);

-- Tabela Endereço: um registro por endereço geocodificável, isto é, por
-- combinação de logradouro, número e localização. O complemento NÃO fica aqui,
-- para não duplicar a coordenada nos edifícios verticais (um prédio de 200
-- apartamentos ocupa uma única linha, não 200). As unidades vão na tabela
-- unidade. O campo n_unidades registra quantas linhas de origem compartilham a
-- coordenada e dispersao_m registra o quanto os registros consolidados nesse
-- endereço discordavam entre si sobre a posição.
CREATE TABLE IF NOT EXISTS endereco (
    id_endereco BIGINT PRIMARY KEY,
    id_fonte INTEGER REFERENCES fonte(id_fonte),

    -- Componentes textuais
    logradouro VARCHAR(255) NOT NULL,
    numero VARCHAR(50),
    bairro VARCHAR(100),
    cep VARCHAR(15),
    municipio VARCHAR(100),
    uf CHAR(2),

    -- Indicadores experimentais, sem garantia de calibração posicional
    lci NUMERIC(4,3),
    mci NUMERIC(4,3),
    cdi INTEGER,
    gci NUMERIC(4,3),

    -- Contagem de registros de origem, sem prova de unidades distintas
    n_unidades INTEGER DEFAULT 1,

    -- Coordenadas originais
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),

    -- Geometria espacial (SRID 4326 - WGS84)
    geom GEOMETRY(Point, 4326)
);

-- Colunas acrescentadas depois da primeira versão do esquema. O ADD COLUMN IF
-- NOT EXISTS permite reaplicar o arquivo sobre um banco já carregado.
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS numero_norm INTEGER;
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS codigo_municipio CHAR(7);
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS n_coordenadas INTEGER DEFAULT 1;
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS dispersao_m NUMERIC(8,2) DEFAULT 0;
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS bairro_norm VARCHAR(100);
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS tipo_logradouro VARCHAR(20);
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS nome_logradouro VARCHAR(255);
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS versao_fonte VARCHAR(80);
ALTER TABLE endereco ADD COLUMN IF NOT EXISTS chave_carga CHAR(64);

CREATE SEQUENCE IF NOT EXISTS endereco_id_seq AS BIGINT;
ALTER TABLE endereco ALTER COLUMN id_endereco SET DEFAULT nextval('endereco_id_seq');
SELECT setval('endereco_id_seq', GREATEST(COALESCE((SELECT max(id_endereco) FROM endereco), 0),
    (SELECT last_value FROM endereco_id_seq)), true);
CREATE UNIQUE INDEX IF NOT EXISTS idx_endereco_chave_carga
    ON endereco(id_fonte, codigo_municipio, versao_fonte, chave_carga)
    WHERE chave_carga IS NOT NULL;

COMMENT ON COLUMN endereco.numero_norm IS
    'Número do imóvel em dígitos, sem zeros à esquerda, para casamento exato e ordenação por proximidade de numeração';
COMMENT ON COLUMN endereco.codigo_municipio IS
    'Código IBGE do município, chave estável para operação nacional';
COMMENT ON COLUMN endereco.n_coordenadas IS
    'Coordenadas distintas da fonte que foram consolidadas neste endereço';
COMMENT ON COLUMN endereco.n_unidades IS
    'Quantidade de registros de origem agrupados, não quantidade de unidades distintas';
COMMENT ON COLUMN endereco.tipo_logradouro IS
    'Tipo do logradouro separado do nome (RUA, AVENIDA, PRACA), para conciliação entre fontes';
COMMENT ON COLUMN endereco.nome_logradouro IS
    'Nome do logradouro sem o tipo, contraparte de tipo_logradouro';
COMMENT ON COLUMN endereco.bairro_norm IS
    'Bairro em forma canônica, usado para desempatar logradouros homônimos a partir do texto consultado';
COMMENT ON COLUMN endereco.dispersao_m IS
    'Diagonal da caixa de abrangência do grupo em metros, que pode superar o raio de ligação';
COMMENT ON COLUMN endereco.chave_carga IS
    'Hash dos índices originais consolidados. Estável para a mesma versão e arquivo de origem';

-- Tabela Unidade: os complementos (apartamentos, salas, lojas) que compartilham
-- a coordenada de um mesmo endereço. Mantê-los separados evita duplicar o ponto
-- geocodificável e preserva a informação de complemento.
CREATE TABLE IF NOT EXISTS unidade (
    id_unidade BIGINT PRIMARY KEY,
    id_endereco BIGINT REFERENCES endereco(id_endereco),
    complemento VARCHAR(150)
);
CREATE SEQUENCE IF NOT EXISTS unidade_id_seq AS BIGINT;
ALTER TABLE unidade ALTER COLUMN id_unidade SET DEFAULT nextval('unidade_id_seq');
SELECT setval('unidade_id_seq', GREATEST(COALESCE((SELECT max(id_unidade) FROM unidade), 0),
    (SELECT last_value FROM unidade_id_seq)), true);

CREATE TABLE IF NOT EXISTS registro_origem (
    id_fonte INTEGER NOT NULL REFERENCES fonte(id_fonte),
    codigo_municipio CHAR(7) NOT NULL,
    versao_fonte VARCHAR(80) NOT NULL,
    origem_idx BIGINT NOT NULL,
    origem_id VARCHAR(100),
    id_endereco BIGINT NOT NULL REFERENCES endereco(id_endereco),
    complemento VARCHAR(150),
    lci NUMERIC(4,3),
    mci NUMERIC(4,3),
    cdi INTEGER,
    gci NUMERIC(4,3),
    PRIMARY KEY (id_fonte, codigo_municipio, versao_fonte, origem_idx)
);
ALTER TABLE registro_origem ADD COLUMN IF NOT EXISTS lci NUMERIC(4,3);
ALTER TABLE registro_origem ADD COLUMN IF NOT EXISTS mci NUMERIC(4,3);
ALTER TABLE registro_origem ADD COLUMN IF NOT EXISTS cdi INTEGER;
ALTER TABLE registro_origem ADD COLUMN IF NOT EXISTS gci NUMERIC(4,3);
CREATE INDEX IF NOT EXISTS idx_registro_origem_endereco ON registro_origem(id_endereco);

CREATE TABLE IF NOT EXISTS carga_repositorio (
    id_fonte INTEGER NOT NULL REFERENCES fonte(id_fonte),
    codigo_municipio CHAR(7) NOT NULL,
    versao_fonte VARCHAR(80) NOT NULL,
    arquivo_sha256 CHAR(64) NOT NULL,
    qualidade_sha256 CHAR(64),
    processamento_sha256 CHAR(64),
    n_fonte BIGINT NOT NULL,
    n_validos BIGINT NOT NULL,
    n_enderecos BIGINT NOT NULL,
    n_complementos BIGINT NOT NULL,
    data_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_fonte, codigo_municipio, versao_fonte)
);
ALTER TABLE carga_repositorio ADD COLUMN IF NOT EXISTS processamento_sha256 CHAR(64);

-- Contabilização de uso da API. Fica no banco, e não em memória, para que o
-- consumo sobreviva ao reinício do serviço e possa ser apurado por cliente.
CREATE TABLE IF NOT EXISTS uso_api (
    id_uso BIGSERIAL PRIMARY KEY,
    momento TIMESTAMPTZ NOT NULL DEFAULT now(),
    rota VARCHAR(60) NOT NULL,
    metodo VARCHAR(10) NOT NULL,
    status INTEGER,
    latencia_ms INTEGER,
    cliente VARCHAR(80) NOT NULL DEFAULT 'anonimo',
    resultados INTEGER
);

-- Índices de alta performance
-- 1. Índice espacial para buscas por raio (ST_DWithin) e vizinho mais próximo
CREATE INDEX IF NOT EXISTS idx_endereco_geom ON endereco USING GIST (geom);

-- 2. Índice trigrama para fuzzy matching de logradouros. É usado pelo operador
--    de similaridade (%); predicados na forma similarity(a, b) >= x NÃO usam
--    este índice e degradam a consulta para varredura sequencial.
CREATE INDEX IF NOT EXISTS idx_endereco_logradouro_trgm
    ON endereco USING GIN (logradouro gin_trgm_ops);

-- 3. Índice para filtragem rápida por fonte (CNEFE vs BHMap)
CREATE INDEX IF NOT EXISTS idx_endereco_fonte ON endereco(id_fonte);

-- 4. Índice para recuperar as unidades de um endereço
CREATE INDEX IF NOT EXISTS idx_unidade_endereco ON unidade(id_endereco);

-- 5. Recorte territorial: sem ele a consulta nacional varre municípios inteiros
CREATE INDEX IF NOT EXISTS idx_endereco_municipio ON endereco(uf, municipio);
CREATE INDEX IF NOT EXISTS idx_endereco_codigo_municipio ON endereco(codigo_municipio);

-- 6. Casamento exato de número dentro do logradouro
CREATE INDEX IF NOT EXISTS idx_endereco_logradouro_numero
    ON endereco(logradouro, numero_norm);

-- 7. Dimensão de logradouros distintos.
-- A busca textual do usuário é por nome de via, e as vias distintas são duas
-- ordens de grandeza menos numerosas que os endereços. Pesquisar o trigrama
-- aqui e só depois recuperar os números do logradouro escolhido evita
-- recalcular similaridade para cada endereço da via.
CREATE MATERIALIZED VIEW IF NOT EXISTS logradouro_busca AS
SELECT codigo_municipio, municipio, uf, logradouro, count(*) AS n_enderecos
FROM endereco
GROUP BY codigo_municipio, municipio, uf, logradouro;

-- O planejador subestima o custo do operador de similaridade e, numa tabela
-- pequena como a de logradouros de um município, escolhe varredura sequencial
-- em vez do índice de trigrama. Declarar o custo real do operador corrige a
-- escolha: na carga de Belo Horizonte a consulta cai de cerca de 41 ms para
-- cerca de 2 ms. Sem isso, o índice existe mas não é usado.
ALTER FUNCTION similarity_op(text, text) COST 500;

CREATE INDEX IF NOT EXISTS idx_logradouro_busca_trgm
    ON logradouro_busca USING GIN (logradouro gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_logradouro_busca_municipio
    ON logradouro_busca (codigo_municipio);
CREATE UNIQUE INDEX IF NOT EXISTS idx_logradouro_busca_chave
    ON logradouro_busca (codigo_municipio, logradouro);

-- 8. Apuração de uso por período e por cliente
CREATE INDEX IF NOT EXISTS idx_uso_api_momento ON uso_api(momento DESC);
CREATE INDEX IF NOT EXISTS idx_uso_api_cliente ON uso_api(cliente, momento DESC);

-- Inserção de fontes padrão (uma vez só)
INSERT INTO fonte (nome, descricao)
SELECT 'CNEFE_2022', 'Cadastro Nacional de Endereços para Fins Estatísticos (GPS) - IBGE 2022'
WHERE NOT EXISTS (SELECT 1 FROM fonte WHERE nome = 'CNEFE_2022');

INSERT INTO fonte (nome, descricao)
SELECT 'BHMAP_EXISTENTE', 'Base oficial de lotes e endereços de Belo Horizonte com filtro de existência'
WHERE NOT EXISTS (SELECT 1 FROM fonte WHERE nome = 'BHMAP_EXISTENTE');
