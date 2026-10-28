"""Carga do CNEFE no repositório de endereços de referência.

A carga faz duas consolidações distintas, e a diferença entre elas é o
argumento do modelo de dados:

1. Vertical, pelo complemento. Todas as unidades de um edifício compartilham a
   mesma coordenada, então o endereço geocodificável entra uma vez em
   `endereco` e os complementos vão para `unidade`. Um prédio de 200
   apartamentos ocupa uma linha, não 200.

2. Horizontal, pela dispersão da coordenada. O mesmo endereço aparece na fonte
   com coordenadas ligeiramente diferentes, e o arredondamento usado na versão
   anterior desta carga (cerca de 1 m) partia esses registros em linhas
   distintas, com indicadores de qualidade contraditórios para o mesmo imóvel.
   Aqui os registros de uma mesma chave de endereço são ligados por pares a até
   `--raio-fusao` metros. Cada componente conexa vira um ponto, escolhido por
   proximidade do centro do grupo. A dispersão total pode superar esse raio.

A entrada é o CNEFE completo. Métricas de avaliação podem ser anexadas pelo
índice original sem excluir registros não avaliados. A substituição no banco é
restrita à fonte, ao município e à versão, dentro de uma transação. A tabela
`registro_origem` preserva cada linha recebida, inclusive identificadores de
origem repetidos. `n_unidades` conta linhas da fonte, não unidades distintas.

Uso:
    python scripts/load_cnefe_to_postgis.py
    python scripts/load_cnefe_to_postgis.py --municipio "Curitiba" --uf PR \
        --codigo-ibge 4106902 --parquet data/processed/cnefe_curitiba.parquet
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.env import database_url
from src.normalize import normalize_cep, normalize_logradouro, partes_endereco, separar_tipo_logradouro
from src.config import PROCESSED_DIR

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESQUEMA_SQL = os.path.join(RAIZ, 'src', 'db', 'init.sql')

# CRS métrico para a fusão por distância. SIRGAS 2000 / UTM 23S cobre BH; para
# outros municípios o argumento --crs-metrico ajusta o fuso.
CRS_METRICO_PADRAO = 'EPSG:31983'


def argumentos():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--parquet', default=str(PROCESSED_DIR / 'cnefe_bh.parquet'),
                   help='CNEFE completo, independente do pareamento municipal')
    p.add_argument('--qualidade-parquet', default=None,
                   help='Métricas opcionais vinculadas por idx_cnefe_original')
    p.add_argument('--municipio', default='Belo Horizonte')
    p.add_argument('--uf', default='MG')
    p.add_argument('--codigo-ibge', default='3106200',
                   help='Código IBGE do município, chave estável para operação nacional')
    p.add_argument('--fonte', default='CNEFE_2022',
                   help='Nome da fonte em `fonte.nome`')
    p.add_argument('--versao-fonte', default='2022')
    p.add_argument('--raio-fusao', type=float, default=30.0,
                   help='Distância máxima por ligação da componente conexa, em metros')
    p.add_argument('--crs-metrico', default=CRS_METRICO_PADRAO)
    return p.parse_args()


def aplicar_esquema(engine):
    with open(ESQUEMA_SQL, encoding='utf-8') as f:
        sql = f.read()
    with engine.begin() as conn:
        conn.execute(text(sql))


def id_da_fonte(conn, nome):
    achado = conn.execute(text("SELECT id_fonte FROM fonte WHERE nome = :n"),
                          {'n': nome}).fetchone()
    if achado:
        return achado[0]
    novo = conn.execute(
        text("INSERT INTO fonte (nome, descricao) VALUES (:n, :d) RETURNING id_fonte"),
        {'n': nome, 'd': f'Fonte registrada automaticamente pela carga: {nome}'},
    ).fetchone()
    return novo[0]


def interpretar_lograd_num(valor):
    """Usa o parser da consulta e retém sufixo e complemento da fonte."""
    if pd.isna(valor):
        return '', None, None
    logradouro, numero_base, _ = partes_endereco(valor)
    if numero_base is None:
        return logradouro, None, None
    campos = re.split(r'[,;]| - ', str(valor))
    padrao = re.compile(r'^\s*(?:N[ºO°]?\.?\s*)?(\d{1,6})\s*([A-Za-z]?)\s*$')
    pos_numero = None
    sufixo = ''
    for i, campo in enumerate(campos[1:], start=1):
        match = padrao.fullmatch(campo)
        if match and str(int(match.group(1))) + match.group(2).upper() == numero_base:
            pos_numero, sufixo = i, match.group(2).upper()
            break
    complemento = ', '.join(c.strip() for c in campos[pos_numero + 1:] if c.strip()) if pos_numero is not None else None
    return logradouro, numero_base, complemento or None


def preparar_registros(df, args):
    """Um registro por linha da fonte, com logradouro canônico e número normalizado."""
    rec = gpd.GeoDataFrame(geometry=df.geometry, crs=df.crs)

    partes = df['LOGRAD_NUM'].map(interpretar_lograd_num)
    logradouro = partes.map(lambda p: p[0])
    numero = partes.map(lambda p: p[1])
    complemento_endereco = partes.map(lambda p: p[2])

    # Forma canônica do logradouro. Garante consistência entre fontes; no CNEFE,
    # que já vem por extenso e sem acento, é quase idempotente.
    rec['logradouro'] = logradouro.map(normalize_logradouro).str.slice(0, 255)
    # Componentes do logradouro: guardar tipo e nome separados permite conciliar
    # fontes que escrevem a mesma via de formas diferentes
    componentes = rec['logradouro'].map(separar_tipo_logradouro)
    rec['tipo_logradouro'] = componentes.map(lambda p: p[0]).astype('object')
    rec['nome_logradouro'] = componentes.map(lambda p: p[1]).astype('object').str.slice(0, 255)
    rec['numero'] = numero.str.slice(0, 50)
    rec['numero_norm'] = pd.to_numeric(
        numero.str.extract(r'(\d+)')[0], errors='coerce').astype('Int64')

    complemento_fonte = df['COMPLEMENTO'] if 'COMPLEMENTO' in df.columns else pd.Series(None, index=df.index)
    rec['complemento'] = pd.Series([
        ', '.join(str(p) for p in (a, b) if pd.notna(p) and str(p).strip())[:150] or None
        for a, b in zip(complemento_endereco, complemento_fonte)
    ], index=df.index)
    rec['bairro'] = df['NOME_BAIRR'].str.slice(0, 100) if 'NOME_BAIRR' in df.columns else None
    # Forma canônica do bairro: permite desempatar logradouros homônimos com o
    # texto que o usuário digitou, sem depender de acentuação ou caixa
    rec['bairro_norm'] = (rec['bairro'].map(normalize_logradouro).str.slice(0, 100)
                          if rec['bairro'] is not None else None)
    # CEP em oito digitos; valores incompletos entram como nulos em vez de
    # serem armazenados como se fossem validos
    rec['cep'] = df['CEP'].map(normalize_cep) if 'CEP' in df.columns else None

    # Município: vem do dado quando a fonte é multi-município, senão do argumento
    rec['municipio'] = (df['MUNICIPIO'].str.slice(0, 100) if 'MUNICIPIO' in df.columns
                        else args.municipio)
    rec['uf'] = df['UF'].str.slice(0, 2) if 'UF' in df.columns else args.uf
    rec['codigo_municipio'] = (df['COD_MUNICIPIO'].astype(str).str.slice(0, 7)
                               if 'COD_MUNICIPIO' in df.columns else args.codigo_ibge)

    rec['origem_idx'] = df.index.to_numpy()
    rec['origem_id'] = (df['COD_UNICO_ENDERECO'].where(df['COD_UNICO_ENDERECO'].notna()).astype('string')
                        if 'COD_UNICO_ENDERECO' in df.columns
                        else pd.Series(None, index=df.index))
    rec['lci'] = df['LCI'] if 'LCI' in df.columns else None
    rec['mci'] = df['MCI'] if 'MCI' in df.columns else None
    rec['cdi'] = df['cdi'] if 'cdi' in df.columns else None
    rec['gci'] = df['GCI_empirico'] if 'GCI_empirico' in df.columns else None
    return rec


def agrupar_por_endereco(rec, raio_fusao, crs_metrico):
    """Atribui um identificador de endereço a cada registro.

    Dentro de cada chave (município, logradouro, número) os registros são
    ligados quando estão a até `raio_fusao` metros um do outro, e cada
    componente conexo vira um endereço. Registros da mesma chave em locais
    distantes, como homônimos de logradouro, permanecem separados.
    """
    metrico = rec.to_crs(crs_metrico)
    x = metrico.geometry.x.to_numpy()
    y = metrico.geometry.y.to_numpy()

    chave = (rec['codigo_municipio'].astype(str) + '|' + rec['logradouro'].fillna('')
             + '|' + rec['numero'].fillna(''))
    codigo_chave = pd.factorize(chave)[0]

    ordem = np.argsort(codigo_chave, kind='stable')
    chaves_ordenadas = codigo_chave[ordem]
    inicios = np.searchsorted(chaves_ordenadas, np.arange(chaves_ordenadas[-1] + 2))

    grupo = np.full(len(rec), -1, dtype=np.int64)
    proximo = 0
    for k in range(len(inicios) - 1):
        posicoes = ordem[inicios[k]:inicios[k + 1]]
        if len(posicoes) == 0:
            continue
        if len(posicoes) == 1:
            grupo[posicoes] = proximo
            proximo += 1
            continue

        pontos = np.column_stack([x[posicoes], y[posicoes]])
        # Registros na mesma coordenada são maioria; a árvore resolve o resto
        arvore = cKDTree(pontos)
        pares = arvore.query_pairs(raio_fusao, output_type='ndarray')
        if len(pares) == 0:
            grupo[posicoes] = proximo + np.arange(len(posicoes))
            proximo += len(posicoes)
            continue

        n = len(posicoes)
        adjacencia = coo_matrix(
            (np.ones(len(pares)), (pares[:, 0], pares[:, 1])), shape=(n, n))
        _, rotulos = connected_components(adjacencia, directed=False)
        grupo[posicoes] = proximo + rotulos
        proximo += rotulos.max() + 1

    return grupo, x, y


def consolidar(rec, grupo, x, y):
    """Escolhe o ponto representativo de cada endereço e mede a dispersão interna."""
    tabela = pd.DataFrame({'grupo': grupo, 'x': x, 'y': y}, index=rec.index)
    centro = tabela.groupby('grupo')[['x', 'y']].transform('mean')
    tabela['dist_centro'] = np.hypot(tabela['x'] - centro['x'], tabela['y'] - centro['y'])

    representante = tabela.groupby('grupo')['dist_centro'].idxmin()

    agregado = tabela.groupby('grupo').agg(
        n_unidades=('x', 'size'),
        x_min=('x', 'min'), x_max=('x', 'max'),
        y_min=('y', 'min'), y_max=('y', 'max'),
    )
    agregado['dispersao_m'] = np.hypot(agregado['x_max'] - agregado['x_min'],
                                       agregado['y_max'] - agregado['y_min']).round(2)
    agregado['n_coordenadas'] = tabela.groupby('grupo').apply(
        lambda g: len(np.unique(np.column_stack([g['x'].round(1), g['y'].round(1)]), axis=0)),
        include_groups=False)

    endereco = rec.loc[representante.values].copy()
    endereco['grupo'] = representante.index.to_numpy()
    endereco['n_unidades'] = agregado['n_unidades'].to_numpy()
    endereco['n_coordenadas'] = agregado['n_coordenadas'].to_numpy()
    endereco['dispersao_m'] = agregado['dispersao_m'].to_numpy()
    return endereco, tabela['grupo']


def anexar_qualidade(df, caminho):
    if not caminho:
        return df
    colunas = ['idx_cnefe_original', 'LCI', 'MCI', 'cdi', 'GCI_empirico']
    qualidade = pd.read_parquet(caminho, columns=colunas)
    if qualidade['idx_cnefe_original'].isna().any() or qualidade['idx_cnefe_original'].duplicated().any():
        raise ValueError('A chave idx_cnefe_original da qualidade deve ser única e não nula')
    qualidade = qualidade.set_index('idx_cnefe_original')
    for coluna in colunas[1:]:
        df[coluna] = df.index.map(qualidade[coluna])
    return df


def chaves_de_grupo(rec, grupos):
    indices = pd.DataFrame({'grupo': grupos.to_numpy(), 'origem_idx': rec['origem_idx'].to_numpy()})
    return indices.groupby('grupo', sort=False)['origem_idx'].agg(
        lambda valores: hashlib.sha256(','.join(map(str, sorted(valores))).encode()).hexdigest()
    )


def hash_arquivo(caminho):
    resumo = hashlib.sha256()
    with open(caminho, 'rb') as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b''):
            resumo.update(bloco)
    return resumo.hexdigest()


def hash_processamento(args):
    """Identifica código e parâmetros que transformam o parquet em endereços."""
    arquivos = [__file__, os.path.join(RAIZ, 'src', 'normalize.py')]
    definicao = {
        'arquivos': {os.path.relpath(caminho, RAIZ): hash_arquivo(caminho)
                     for caminho in arquivos},
        'raio_fusao': args.raio_fusao,
        'crs_metrico': args.crs_metrico,
        'pandas': pd.__version__,
        'geopandas': gpd.__version__,
        'numpy': np.__version__,
    }
    return hashlib.sha256(json.dumps(definicao, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def promover_carga(engine, args, endereco, unidade, origens, manifesto=None):
    """Substitui apenas a fonte, município e versão em uma transação."""
    if manifesto is None:
        raise ValueError('Manifesto obrigatório para promover a carga')
    for campo in ('arquivo_sha256', 'processamento_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', str(manifesto.get(campo, ''))):
            raise ValueError(f'Hash inválido no manifesto: {campo}')
    qualidade_hash = manifesto.get('qualidade_sha256')
    if qualidade_hash is not None and not re.fullmatch(r'[0-9a-f]{64}', str(qualidade_hash)):
        raise ValueError('Hash inválido no manifesto: qualidade_sha256')
    contagens = [manifesto.get(campo) for campo in
                 ('n_fonte', 'n_validos', 'n_enderecos', 'n_complementos')]
    if (any(type(valor) is not int or valor < 0 for valor in contagens)
            or not (contagens[0] >= contagens[1] >= contagens[2] > 0)
            or contagens[3] > contagens[1]):
        raise ValueError('Contagens inválidas no manifesto')
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(916742001)"))
        id_fonte = id_da_fonte(conn, args.fonte)
        escopo = {'f': id_fonte, 'm': args.codigo_ibge, 'v': args.versao_fonte}
        antigos = pd.read_sql(text("SELECT id_endereco, chave_carga FROM endereco "
                                   "WHERE id_fonte = :f AND codigo_municipio = :m "
                                   "AND versao_fonte = :v AND chave_carga IS NOT NULL"), conn, params=escopo)
        mapa = dict(zip(antigos['chave_carga'], antigos['id_endereco']))
        endereco['id_endereco'] = endereco['chave_carga'].map(mapa)
        novos = endereco['id_endereco'].isna()
        if novos.any():
            reservados = conn.execute(text("SELECT nextval('endereco_id_seq') "
                                           "FROM generate_series(1, :n)"), {'n': int(novos.sum())}).scalars().all()
            endereco.loc[novos, 'id_endereco'] = reservados
        endereco['id_endereco'] = endereco['id_endereco'].astype('int64')
        ids = endereco.set_index('grupo')['id_endereco']
        unidade['id_endereco'] = unidade['grupo'].map(ids).astype('int64')
        origens['id_endereco'] = origens['grupo'].map(ids).astype('int64')
        unidades_antigas = pd.read_sql(text(
            "SELECT u.id_unidade, u.id_endereco, u.complemento FROM unidade u "
            "JOIN endereco e ON e.id_endereco = u.id_endereco "
            "WHERE e.id_fonte = :f AND e.codigo_municipio = :m "
            "AND e.versao_fonte = :v ORDER BY u.id_unidade"), conn, params=escopo)
        chaves_unidade = ['id_endereco', 'complemento']
        unidades_antigas['ocorrencia'] = unidades_antigas.groupby(chaves_unidade, dropna=False).cumcount()
        unidades_novas = unidade[chaves_unidade].copy()
        unidades_novas['ocorrencia'] = unidades_novas.groupby(chaves_unidade, dropna=False).cumcount()
        unidade['id_unidade'] = unidades_novas.merge(
            unidades_antigas, on=chaves_unidade + ['ocorrencia'], how='left',
            validate='1:1', sort=False)['id_unidade'].to_numpy()
        novas_unidades = unidade['id_unidade'].isna()
        if novas_unidades.any():
            reservados_unidade = conn.execute(text("SELECT nextval('unidade_id_seq') "
                "FROM generate_series(1, :n)"), {'n': int(novas_unidades.sum())}).scalars().all()
            unidade.loc[novas_unidades, 'id_unidade'] = reservados_unidade
        unidade['id_unidade'] = unidade['id_unidade'].astype('int64')
        endereco['id_fonte'] = id_fonte
        origens['id_fonte'] = id_fonte

        conn.execute(text("DELETE FROM registro_origem WHERE id_fonte = :f "
                          "AND codigo_municipio = :m AND versao_fonte = :v"), escopo)
        conn.execute(text("DELETE FROM unidade WHERE id_endereco IN "
                          "(SELECT id_endereco FROM endereco WHERE id_fonte = :f "
                          "AND codigo_municipio = :m AND "
                          "(versao_fonte = :v OR versao_fonte IS NULL))"), escopo)
        conn.execute(text("DELETE FROM endereco WHERE id_fonte = :f "
                          "AND codigo_municipio = :m AND "
                          "(versao_fonte = :v OR versao_fonte IS NULL)"), escopo)

        colunas_endereco = ['id_endereco', 'id_fonte', 'versao_fonte', 'chave_carga',
                            'logradouro', 'numero', 'numero_norm', 'tipo_logradouro',
                            'nome_logradouro', 'bairro', 'bairro_norm', 'cep', 'municipio',
                            'uf', 'codigo_municipio', 'lci', 'mci', 'cdi', 'gci',
                            'n_unidades', 'n_coordenadas', 'dispersao_m',
                            'latitude', 'longitude', 'geometry']
        geodados = gpd.GeoDataFrame(endereco[colunas_endereco], geometry='geometry', crs=4326)
        geodados = geodados.rename_geometry('geom')
        # A associação parcial de qualidade produz float com NaN. COPY exige
        # inteiros sem sufixo decimal, preservando SQL NULL onde não há CDI.
        # A conversão também rejeita valores fracionários em vez de truncá-los.
        geodados['cdi'] = geodados['cdi'].astype('Int64')
        origens['cdi'] = origens['cdi'].astype('Int64')
        geodados.to_postgis('endereco', con=conn, if_exists='append', index=False, chunksize=25000)
        unidade[['id_unidade', 'id_endereco', 'complemento']].to_sql(
            'unidade', con=conn, if_exists='append', index=False, chunksize=50000)
        origens[['id_fonte', 'codigo_municipio', 'versao_fonte', 'origem_idx',
                 'origem_id', 'id_endereco', 'complemento', 'lci', 'mci', 'cdi', 'gci']].to_sql(
            'registro_origem', con=conn, if_exists='append', index=False, chunksize=50000)
        conn.execute(text("INSERT INTO carga_repositorio "
                              "(id_fonte, codigo_municipio, versao_fonte, arquivo_sha256, "
                              "qualidade_sha256, processamento_sha256, n_fonte, n_validos, "
                              "n_enderecos, n_complementos) "
                              "VALUES (:f, :m, :v, :arquivo_sha256, :qualidade_sha256, "
                              ":processamento_sha256, "
                              ":n_fonte, :n_validos, :n_enderecos, :n_complementos) "
                              "ON CONFLICT (id_fonte, codigo_municipio, versao_fonte) "
                              "DO UPDATE SET arquivo_sha256 = EXCLUDED.arquivo_sha256, "
                              "qualidade_sha256 = EXCLUDED.qualidade_sha256, "
                              "processamento_sha256 = EXCLUDED.processamento_sha256, "
                              "n_fonte = EXCLUDED.n_fonte, n_validos = EXCLUDED.n_validos, "
                              "n_enderecos = EXCLUDED.n_enderecos, "
                              "n_complementos = EXCLUDED.n_complementos, data_carga = now()"),
                     {**escopo, **manifesto})
        conn.execute(text("REFRESH MATERIALIZED VIEW logradouro_busca"))
        vias = conn.execute(text("SELECT count(*) FROM logradouro_busca")).scalar()
    return vias


def carregar():
    args = argumentos()
    inicio = time.time()
    engine = create_engine(database_url())

    print('1. Aplicando esquema (idempotente)...')
    aplicar_esquema(engine)
    print(f'2. Lendo {args.parquet}...')
    df = gpd.read_parquet(args.parquet)
    print(f'   Registros na fonte: {len(df):,}')
    if 'idx_cnefe_original' in df.columns:
        raise ValueError('Use o CNEFE completo como fonte, não o mestre avaliado')
    if (not df.index.is_unique or df.index.hasnans
            or not pd.api.types.is_integer_dtype(df.index.dtype)):
        raise ValueError('O índice original do CNEFE deve ser inteiro, único e não nulo')
    df = anexar_qualidade(df, args.qualidade_parquet)

    print('3. Reprojetando para EPSG:4326 e normalizando os campos...')
    df = df.to_crs(epsg=4326)
    rec = preparar_registros(df, args)
    if rec['codigo_municipio'].isna().any() or set(rec['codigo_municipio'].astype(str)) != {args.codigo_ibge}:
        raise ValueError('A carga deve conter apenas o município informado em --codigo-ibge')
    validos = rec.geometry.notna() & ~rec.geometry.is_empty & rec['logradouro'].fillna('').ne('')
    if not validos.all():
        print(f'   Registros presentes mas inválidos para geocodificação: {(~validos).sum():,}')
        rec = rec.loc[validos].copy()
    if rec.empty:
        raise ValueError('Nenhum endereço válido na fonte')
    rec['longitude'] = rec.geometry.x
    rec['latitude'] = rec.geometry.y

    print(f'4. Agrupando por componente conexa (ligação de até {args.raio_fusao:.0f} m)...')
    grupo, x, y = agrupar_por_endereco(rec, args.raio_fusao, args.crs_metrico)
    endereco, grupo_por_registro = consolidar(rec, grupo, x, y)
    for coluna in ['lci', 'mci', 'cdi', 'gci']:
        valores = rec.groupby(grupo_por_registro)[coluna]
        uniforme = valores.first().where(valores.nunique(dropna=False).eq(1))
        endereco[coluna] = endereco['grupo'].map(uniforme).to_numpy()

    endereco['chave_carga'] = endereco['grupo'].map(chaves_de_grupo(rec, grupo_por_registro))
    endereco['versao_fonte'] = args.versao_fonte

    fundidos = int((endereco['n_coordenadas'] > 1).sum())
    print(f'   {len(rec):,} registros -> {len(endereco):,} endereços '
          f'({len(endereco)/len(rec)*100:.1f}%)')
    print(f'   Endereços que fundiram coordenadas distintas: {fundidos:,} '
          f'({fundidos/len(endereco)*100:.1f}%)')
    print(f'   Dispersão interna: mediana {endereco.loc[endereco.n_coordenadas > 1, "dispersao_m"].median():.2f} m, '
          f'máx {endereco["dispersao_m"].max():.2f} m')

    tem_complemento = (rec['complemento'].notna()
                       & (rec['complemento'].astype(str).str.strip() != ''))
    unidade = pd.DataFrame({
        'grupo': grupo_por_registro[tem_complemento].to_numpy(),
        'complemento': rec.loc[tem_complemento, 'complemento'].to_numpy(),
    })
    origens = pd.DataFrame({
        'grupo': grupo_por_registro.to_numpy(),
        'codigo_municipio': rec['codigo_municipio'].to_numpy(),
        'versao_fonte': args.versao_fonte,
        'origem_idx': rec['origem_idx'].to_numpy(),
        'origem_id': rec['origem_id'].to_numpy(),
        'complemento': rec['complemento'].to_numpy(),
        'lci': rec['lci'].to_numpy(),
        'mci': rec['mci'].to_numpy(),
        'cdi': rec['cdi'].to_numpy(),
        'gci': rec['gci'].to_numpy(),
    })
    if len(origens) != len(rec) or origens['origem_idx'].duplicated().any():
        raise ValueError('Proveniência incompleta ou com índice original repetido')
    if endereco['chave_carga'].isna().any() or endereco['chave_carga'].duplicated().any():
        raise ValueError('Chaves de endereço ausentes ou repetidas')
    print(f'   Registros de origem com complemento: {len(unidade):,}')

    print('5. Gravando e atualizando a busca em uma transação...')
    manifesto = {
        'arquivo_sha256': hash_arquivo(args.parquet),
        'qualidade_sha256': hash_arquivo(args.qualidade_parquet) if args.qualidade_parquet else None,
        'processamento_sha256': hash_processamento(args),
        'n_fonte': len(df),
        'n_validos': len(rec),
        'n_enderecos': len(endereco),
        'n_complementos': len(unidade),
    }
    vias = promover_carga(engine, args, endereco, unidade, origens, manifesto)
    print(f'   Logradouros distintos indexados para busca: {vias:,}')

    print(f'Carga finalizada em {(time.time() - inicio)/60:.2f} minutos.')


if __name__ == '__main__':
    carregar()
