-- Habilita extensões necessárias para o repositório de endereços de referência
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tabela Fonte: mapeia as diferentes origens dos dados (ex: CNEFE, BHMap).
-- O esquema é multi-fonte por construção: novas bases entram sem alterar o modelo.
CREATE TABLE fonte (
    id_fonte SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela Endereço: um registro por endereço geocodificável, isto é, por
-- combinação de logradouro, número e coordenada. O complemento NÃO fica aqui,
-- para não duplicar a coordenada nos edifícios verticais (um prédio de 200
-- apartamentos ocupa uma única linha, não 200). As unidades vão na tabela
-- unidade. O campo n_unidades registra quantas unidades compartilham a coordenada.
CREATE TABLE endereco (
    id_endereco BIGINT PRIMARY KEY,
    id_fonte INTEGER REFERENCES fonte(id_fonte),

    -- Componentes textuais
    logradouro VARCHAR(255) NOT NULL,
    numero VARCHAR(50),
    bairro VARCHAR(100),
    cep VARCHAR(15),
    municipio VARCHAR(100),
    uf CHAR(2),

    -- Confiança delimitada (qualidade posicional calibrada)
    lci NUMERIC(4,3),
    mci NUMERIC(4,3),
    cdi INTEGER,
    gci NUMERIC(4,3),

    -- Unidades que compartilham a mesma coordenada (verticalização)
    n_unidades INTEGER DEFAULT 1,

    -- Coordenadas originais
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),

    -- Geometria espacial (SRID 4326 - WGS84)
    geom GEOMETRY(Point, 4326)
);

-- Tabela Unidade: os complementos (apartamentos, salas, lojas) que compartilham
-- a coordenada de um mesmo endereço. Mantê-los separados evita duplicar o ponto
-- geocodificável e preserva a informação de complemento.
CREATE TABLE unidade (
    id_unidade BIGINT PRIMARY KEY,
    id_endereco BIGINT REFERENCES endereco(id_endereco),
    complemento VARCHAR(150)
);

-- Índices de alta performance
-- 1. Índice espacial para buscas por raio (ST_DWithin) e vizinho mais próximo
CREATE INDEX idx_endereco_geom ON endereco USING GIST (geom);

-- 2. Índice trigrama para fuzzy matching de logradouros (geocodificação aproximada)
CREATE INDEX idx_endereco_logradouro_trgm ON endereco USING GIN (logradouro gin_trgm_ops);

-- 3. Índice para filtragem rápida por fonte (CNEFE vs BHMap)
CREATE INDEX idx_endereco_fonte ON endereco(id_fonte);

-- 4. Índice para recuperar as unidades de um endereço
CREATE INDEX idx_unidade_endereco ON unidade(id_endereco);

-- Inserção de fontes padrão
INSERT INTO fonte (nome, descricao) VALUES
('CNEFE_2022', 'Cadastro Nacional de Endereços para Fins Estatísticos (GPS) - IBGE 2022'),
('BHMAP_EXISTENTE', 'Base oficial de lotes e endereços de Belo Horizonte com filtro de existência');
