"""
metrics.py — Métricas de Qualidade da Geocodificação
Componentes adaptados localmente do GCI de Davis e Fonseca (2007) e métricas ISO 19157.

Implementa: LCI, MCI, PCI, GCI, Completude, RMSE, CE90
Métricas de coordenada (intrínsecas): CCR, CDI, DRS, PCI_empirico
"""
import numpy as np
import pandas as pd
from rapidfuzz import fuzz


# ============================================================
# LCI — Locating Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_lci(nv_geo_coord_series, weights_map=None):
    """
    Adaptação local de LCI, com pesos históricos não calibrados.

    NV_GEO_COORD identifica procedimentos, não uma escala de erro observado:
    1 original do Censo, 2 modificada pelo agrupamento de apartamentos,
    3 estimada por ausência ou invalidade da original, 4 face de quadra,
    5 localidade e 6 setor censitário. O mapa numérico é mantido como
    baseline para comparar execuções. Não representa os pesos do IBGE
    nem uma probabilidade validada de acerto.

    Args:
        nv_geo_coord_series: Series com valores NV_GEO_COORD
        weights_map: Dicionário {nível: peso}

    Returns:
        Series com LCI scores (0.0 a 1.0)
    """
    if weights_map is None:
        weights_map = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.3, 6: 0.1}
    return nv_geo_coord_series.map(weights_map).fillna(0.1)


# ============================================================
# Completude — ISO 19157
# ============================================================
def calculate_completude(df, campos_pesos=None):
    """
    Indicador de Completude conforme ISO 19157.
    Avalia a presença/ausência dos atributos críticos do endereço.

    Args:
        df: DataFrame com registros de endereço
        campos_pesos: Dict {nome_coluna: peso}

    Returns:
        Series com scores de completude (0.0 a 1.0)
    """
    if campos_pesos is None:
        campos_pesos = {
            'CEP': 1.5,
            'LOGRAD_NUM': 1.5,
            'COMPLEMENTO': 1.0,
            'DSC_LOCALIDADE': 0.5,
            'NV_GEO_COORD': 0.5,
        }

    total_weight = sum(campos_pesos.values())
    scores = np.zeros(len(df))

    for col, weight in campos_pesos.items():
        if col in df.columns:
            presence = df[col].notna() & (df[col].astype(str).str.strip() != '')
            scores += presence.astype(float) * weight

    return scores / total_weight


# ============================================================
# MCI — Matching Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_mci(distance, textual_sim, max_dist=100.0, alpha=0.5):
    """
    Adaptação local do Matching Certainty Indicator (MCI).
    Combina similaridade textual e distância do candidato CNEFE ↔ BHMap.
    Requer o cadastro BHMap e não é uma métrica intrínseca ao CNEFE.

    MCI = α × Sim_textual + (1-α) × Sim_espacial

    Args:
        distance: Distância euclidiana em metros entre pares
        textual_sim: Similaridade textual (0 a 100, RapidFuzz)
        max_dist: Raio máximo de busca (default 100m)
        alpha: Peso da similaridade textual (default 0.5)

    Returns:
        Series/array com MCI scores (0.0 a 1.0)
    """
    spatial_sim = np.clip(1.0 - (distance / max_dist), 0.0, 1.0)
    textual_sim_norm = np.clip(textual_sim / 100.0, 0.0, 1.0)
    return (alpha * textual_sim_norm) + ((1 - alpha) * spatial_sim)


def calculate_textual_similarity(str1, str2):
    """
    Calcula similaridade textual entre strings de endereço via RapidFuzz.
    Usa token_sort_ratio para robustez contra reordenação de tokens.
    """
    if pd.isna(str1) or pd.isna(str2):
        return 0.0
    return fuzz.token_sort_ratio(str(str1).lower(), str(str2).lower())


# ============================================================
# Peso por tipologia do baseline local, distinto do PCI de parsing de Davis e Fonseca (2007)
# ============================================================
def calculate_pci(df, tipo_col='COD_TIPO_ESPECI', complemento_col='COMPLEMENTO',
                  vertical_score=0.5, horizontal_score=1.0):
    """
    Peso por tipologia do baseline local, mantido com nome PCI por compatibilidade.
    Os pesos de apartamentos e casas são uma escolha deste projeto. Não são o
    Parsing Certainty Indicator definido por Davis e Fonseca (2007) e não
    representam probabilidades calibradas contra erro posicional.

    Usa COD_TIPO_ESPECI (103=Apartamento) e/ou padrões no COMPLEMENTO.

    Args:
        df: DataFrame
        tipo_col: Coluna com sub-tipo do endereço
        complemento_col: Coluna com complemento
        vertical_score: Score PCI para endereços verticais (default 0.5)
        horizontal_score: Score PCI para endereços horizontais (default 1.0)

    Returns:
        Series com PCI scores
    """
    is_vertical = pd.Series(False, index=df.index)

    # Via COD_TIPO_ESPECI (103 = Apartamento)
    if tipo_col in df.columns:
        is_vertical |= (df[tipo_col] == 103).fillna(False)

    # Via COMPLEMENTO (contém "APARTAMENTO", "EDIFÍCIO", "BLOCO", etc.)
    if complemento_col in df.columns:
        pattern = r'apartamento|edif[ií]cio|condom[ií]nio|bloco|sala|loja|andar|cobertura'
        is_vertical |= df[complemento_col].astype(str).str.contains(
            pattern, case=False, na=False
        )

    return np.where(is_vertical.values, vertical_score, horizontal_score)


# ============================================================
# GCI — Geocoding Certainty Indicator (Davis & Fonseca, 2007)
# ============================================================
def calculate_gci(lci, mci, pci):
    """
    Produto local denominado GCI = LCI × MCI × PCI.
    O cálculo depende do MCI obtido com uma referência externa.
    O PCI local por tipologia ou por 1/CDI não equivale ao PCI original de parsing.
    """
    return lci * mci * pci


# ============================================================
# Métricas Posicionais
# ============================================================
def calculate_rmse(distances):
    """Root Mean Square Error das distâncias euclidianas."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.sqrt(np.mean(np.square(d)))


def calculate_ce90(distances):
    """Circular Error 90%: raio que contém 90% dos erros."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.percentile(d, 90)


def calculate_mae(distances):
    """Mean Absolute Error das distâncias."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.mean(np.abs(d))


def calculate_median_error(distances):
    """Erro mediano — mais robusto que RMSE a outliers."""
    d = np.asarray(distances, dtype=float)
    d = d[~np.isnan(d)]
    return np.median(d)


# ============================================================
# Métricas de Coordenada — qualidade intrínseca do ponto no espaço
# Complementam as métricas de endereço (MCI/GCI) com avaliação
# da coordenada como objeto geográfico, independente de referência externa.
# ============================================================

def calculate_cdi(gdf, coord_precision_m=1):
    """
    CDI — Coordinate Duplication Index.
    Conta quantos registros compartilham a mesma coordenada (arredondada
    à precisão dada em metros). Coincidências podem resultar de unidades
    no mesmo edifício, arredondamento ou localização agregada.

    Valores: n >= 1. CDI=1 indica coordenada não repetida neste conjunto.
    CDI=N indica N registros na mesma posição arredondada.

    Retorna duas Series:
        cdi        : contagem bruta de registros no mesmo ponto
        pci_empirico: 1/cdi ∈ (0, 1], multiplicidade inversa. O nome é histórico.
                       Não é probabilidade calibrada nem PCI de parsing.

    Args:
        gdf: GeoDataFrame com geometria UTM (metros)
        coord_precision_m: arredondamento em metros (default=1m)

    Returns:
        DataFrame com colunas [cdi, pci_empirico] no mesmo índice de gdf
    """
    x = (gdf.geometry.x / coord_precision_m).round().astype(int)
    y = (gdf.geometry.y / coord_precision_m).round().astype(int)
    coord_key = x.astype(str) + "_" + y.astype(str)

    cdi = coord_key.map(coord_key.value_counts())
    pci_empirico = (1.0 / cdi).clip(upper=1.0)

    return pd.DataFrame({'cdi': cdi, 'pci_empirico': pci_empirico}, index=gdf.index)


def calculate_ccr(gdf_cnefe, gdf_setores, setor_col_cnefe='COD_SETOR',
                  setor_col_poly='COD_SETOR', normalize_setor=True):
    """
    CCR — Coordinate Containment Rate (por registro).
    Verifica se a coordenada do CNEFE cai dentro do polígono do setor
    censitário declarado no campo COD_SETOR. Discrepância indica erro
    topológico na coordenada ou atribuição incorreta de setor.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM, com COD_SETOR como atributo)
        gdf_setores: GeoDataFrame dos setores censitários (polígonos UTM)
        setor_col_cnefe: coluna em gdf_cnefe com código do setor declarado
        setor_col_poly: coluna em gdf_setores com código do setor
        normalize_setor: remove sufixo 'P' do CNEFE (formato IBGE vs BHMap)

    Returns:
        Series booleana `within_declared_setor` (True=OK, False=erro topológico)
    """
    import geopandas as gpd

    # Spatial join: descobre em qual setor a coordenada realmente cai
    setores_proj = gdf_setores[[setor_col_poly, 'geometry']].copy()
    setores_proj = setores_proj.rename(columns={setor_col_poly: 'setor_real'})

    joined = gpd.sjoin(
        gdf_cnefe[[setor_col_cnefe, 'geometry']],
        setores_proj,
        how='left',
        predicate='within'
    )

    setor_declarado = joined[setor_col_cnefe].astype(str).str.strip()
    if normalize_setor:
        # CNEFE usa sufixo 'P' (e.g. '310620005630498P'); shapefile não usa
        setor_declarado = setor_declarado.str.rstrip('P').str.rstrip('S')

    setor_real = joined['setor_real'].astype(str).str.strip()

    within = (setor_declarado == setor_real)
    within = within.reindex(gdf_cnefe.index)
    within = within.fillna(False)
    return within


def calculate_drs(gdf_cnefe, gdf_vias, batch_size=50_000):
    """
    DRS — Distance to Road Segment (metros).
    Distância de cada ponto CNEFE ao segmento de via mais próximo.
    Alta DRS indica ponto em área sem logradouro próximo (morro, praça,
    área industrial) ou coordenada deslocada da via declarada.

    Usa sjoin_nearest contra a rede viária (LineStrings UTM).
    Processado em lotes para controlar uso de memória.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM)
        gdf_vias: GeoDataFrame de vias (LineStrings UTM)
        batch_size: tamanho do lote para processamento

    Returns:
        Series float com distância em metros, mesmo índice de gdf_cnefe
    """
    import geopandas as gpd
    from tqdm.auto import tqdm

    vias = gdf_vias[['geometry']].copy()
    results = []
    idx_list = gdf_cnefe.index.tolist()

    for start in tqdm(range(0, len(idx_list), batch_size), desc="  Distância às vias", unit="lote"):
        batch_idx = idx_list[start:start + batch_size]
        batch = gdf_cnefe.loc[batch_idx, ['geometry']]
        joined = gpd.sjoin_nearest(batch, vias, how='left', distance_col='drs')
        # sjoin_nearest pode duplicar se houver empate; manter o menor
        joined = joined[~joined.index.duplicated(keep='first')]
        results.append(joined['drs'])

    drs_series = pd.concat(results)
    drs_series = drs_series.reindex(gdf_cnefe.index)
    return drs_series


def calculate_csi(gdf_cnefe, gdf_setores, setor_col_cnefe='COD_SETOR',
                  setor_col_poly='COD_SETOR', normalize_setor=True):
    """
    CSI — Coordinate Spatial Isolation (metros).
    Distância do ponto CNEFE ao centróide do seu setor censitário declarado.
    Pontos muito distantes do centróide de seu setor são candidatos a erro
    de atribuição ou deslocamento grosseiro de coordenada.

    Args:
        gdf_cnefe: GeoDataFrame CNEFE (UTM)
        gdf_setores: GeoDataFrame dos setores (UTM, polígonos)
        normalize_setor: remove sufixo 'P' do CNEFE (formato IBGE vs BHMap)

    Returns:
        Series float com distância ao centróide do setor (metros)
    """
    setores_centroids = gdf_setores[[setor_col_poly, 'geometry']].copy()
    setores_centroids['centroid'] = setores_centroids.geometry.centroid
    centroid_map = setores_centroids.set_index(setor_col_poly)['centroid'].to_dict()

    setor_declared = gdf_cnefe[setor_col_cnefe].astype(str).str.strip()
    if normalize_setor:
        setor_declared = setor_declared.str.rstrip('P').str.rstrip('S')

    centroids = setor_declared.map(centroid_map)
    valid_mask = centroids.notna()
    distances = pd.Series(np.nan, index=gdf_cnefe.index)

    if valid_mask.any():
        pts = gdf_cnefe.loc[valid_mask, 'geometry']
        ctrs = centroids[valid_mask]
        import geopandas as gpd
        ctrs_gs = gpd.GeoSeries(ctrs, crs=gdf_cnefe.crs)
        distances[valid_mask] = pts.distance(ctrs_gs)

    return distances


# ============================================================
# Pareamento por identidade de endereço
# O pareamento por vizinho mais próximo responde "existe ponto da referência
# perto daqui", que não é a mesma pergunta que "este endereço existe na
# referência e onde ela o coloca". As funções abaixo casam os dois cadastros
# pela identidade do endereço (logradouro canônico e número), sem restrição de
# distância, de modo que o deslocamento medido seja o do mesmo imóvel.
# ============================================================

def chave_identidade(logradouro, numero):
    """Chave de identidade do endereço: (logradouro canônico, número em dígitos).

    O logradouro passa pela forma canônica do repositório (sem acento, caixa
    alta, tipo por extenso). Do número fica apenas a primeira sequência de
    dígitos, sem zeros à esquerda, de modo que '0210', '210' e '210 A'
    convergem para '210'.
    """
    from .normalize import normalize_logradouro

    log = pd.Series(logradouro).map(normalize_logradouro)
    num = (pd.Series(numero).astype(str)
           .str.extract(r'(\d+)')[0]
           .str.lstrip('0')
           .replace('', np.nan))
    return log, num


def separar_logradouro_numero(serie_logrado_num):
    """Separa 'LOGRADOURO, NUMERO' do CNEFE em duas séries.

    O CNEFE traz logradouro e número no mesmo campo, separados por vírgula.
    Em Belo Horizonte todos os 1.180.102 registros têm exatamente uma vírgula,
    mas essa regularidade é do arquivo, não do formato, e a carga é usada em
    outros municípios. Por isso o corte não confia cegamente na última vírgula:
    quando o campo após ela não contém dígito algum, o que indica complemento em
    vez de número, a separação recua para a vírgula anterior.

    Registros sem vírgula ficam inteiros no logradouro e sem número.
    """
    s = pd.Series(serie_logrado_num).astype(str)
    partes = s.str.rsplit(',', n=1, expand=True)
    logradouro = partes[0].str.strip()
    numero = partes[1].str.strip() if partes.shape[1] > 1 else pd.Series(np.nan, index=s.index)
    sem_virgula = numero.isna() if partes.shape[1] > 1 else pd.Series(True, index=s.index)
    logradouro = logradouro.where(~sem_virgula, s.str.strip())

    # Complemento depois do número: um número de imóvel começa por dígito
    # ('100', '55 A'), um complemento não ('SALA 2', 'APTO 301'). Quando o último
    # campo não começa por dígito e ainda resta vírgula antes dele, o corte recua.
    # Só se aplica quando algum registro tem vírgula; caso contrário a série de
    # números é vazia e não há texto a inspecionar.
    if partes.shape[1] > 1:
        suspeito = (~sem_virgula
                    & ~numero.fillna('').str.match(r'^\d')
                    & logradouro.str.contains(',', na=False, regex=False))
        if suspeito.any():
            recuo = logradouro[suspeito].str.rsplit(',', n=1, expand=True)
            logradouro.loc[suspeito] = recuo[0].str.strip()
            numero.loc[suspeito] = recuo[1].str.strip()

    return logradouro, numero


def conciliar_logradouros(nomes_alvo, nomes_referencia, limiar=90, margem=2):
    """Tabela de correspondência entre grafias de logradouro de duas fontes.

    O casamento exato de nomes de via trata como ausente aquilo que é apenas
    grafado de outro modo: TEREZA contra TERESA, PLINIO DE MORAIS contra PLINIO
    MORAES, ou a abreviação BEC no lugar de BECO. Como esse tipo de variação é
    mais frequente em áreas de urbanização informal, ignorá-la não apenas reduz
    a cobertura do pareamento, mas a reduz de forma desigual entre estratos, o
    que enviesa qualquer comparação entre eles.

    A conciliação segue a tradição de casamento aproximado de nomes geográficos
    de Davis Jr. e Salles (2007): compara por similaridade de tokens e aceita a
    correspondência quando o melhor candidato atinge o limiar e está à frente
    do segundo por pelo menos `margem` pontos. Isso reduz a aceitação de
    candidatos com escores próximos, mas não comprova a identidade da via.
    Designadores numéricos e alfabéticos, como PIUM I e PIUM II, não têm
    proteção explícita; a margem não impede uma troca quando falta um
    concorrente adequado na referência.

    Parâmetros
    ----------
    nomes_alvo, nomes_referencia : iteráveis de str
        Nomes canônicos distintos de cada fonte.
    limiar : int
        Similaridade mínima, de 0 a 100, pelo token_sort_ratio.
    margem : int
        Vantagem mínima do melhor candidato sobre o segundo colocado.

    Retorna
    -------
    dict
        Nome do alvo para nome da referência, apenas para os nomes que não
        existem na referência com grafia idêntica e que foram conciliados.
    """
    from rapidfuzz import fuzz, process

    referencia = sorted({n for n in nomes_referencia if n})
    existentes = set(referencia)
    pendentes = sorted({n for n in nomes_alvo if n and n not in existentes})
    if not pendentes or not referencia:
        return {}

    pontuacoes = process.cdist(pendentes, referencia, scorer=fuzz.token_sort_ratio,
                               workers=-1, score_cutoff=max(limiar - 10, 0))
    mapa = {}
    for i, nome in enumerate(pendentes):
        linha = pontuacoes[i]
        melhor = int(linha.argmax())
        maior = linha[melhor]
        if maior < limiar:
            continue
        segundo = np.partition(linha, -2)[-2] if len(linha) > 1 else 0
        if maior - segundo < margem:
            continue
        mapa[nome] = referencia[melhor]
    return mapa


def parear_por_identidade(gdf_alvo, gdf_referencia, chave_alvo, chave_referencia,
                          dispersao_ambigua_m=100.0, mapa_logradouros=None):
    """Casa dois cadastros de endereço pela identidade (logradouro, número).

    Não há restrição de distância: o par é definido pelo endereço, e a
    distância resultante é o deslocamento entre as duas bases para o mesmo
    imóvel. Quando a referência tem mais de um ponto para a mesma chave, fica
    o mais próximo, e a dispersão entre esses candidatos é devolvida para que
    chaves ambíguas (mesmo logradouro e número em pontos distantes, sinal de
    homonímia de logradouro) possam ser isoladas na análise.

    Parâmetros
    ----------
    gdf_alvo, gdf_referencia : GeoDataFrame
        Ambos em CRS métrico e no mesmo CRS.
    chave_alvo, chave_referencia : tuple de duas Series
        Saída de `chave_identidade` para cada lado.
    dispersao_ambigua_m : float
        Distância acima da qual os candidatos de uma mesma chave são
        considerados ambíguos.
    mapa_logradouros : dict, opcional
        Correspondência entre grafias de logradouro, obtida de
        `conciliar_logradouros`. Sem ela, o casamento de nomes é exato e trata
        variações de grafia como ausência no cadastro.

    Retorna
    -------
    DataFrame indexado como `gdf_alvo`, com as colunas:
        dist_identidade  distância ao ponto da referência com o mesmo endereço
        ref_x, ref_y     coordenadas do ponto da referência, no CRS de entrada,
                         para desenhar o vetor de deslocamento
        chave_dispersao  dispersão dos candidatos da chave na referência
        chave_ambigua    True quando a dispersão passa do limite
        pareado_identidade  True quando existe contraparte por identidade
    """
    log_a, num_a = chave_alvo
    log_r, num_r = chave_referencia

    ref = pd.DataFrame({
        'log': log_r.values,
        'num': num_r.values,
        'rx': gdf_referencia.geometry.x.values,
        'ry': gdf_referencia.geometry.y.values,
    }).dropna(subset=['log', 'num'])

    extensao = ref.groupby(['log', 'num'])[['rx', 'ry']].agg(['min', 'max'])
    dispersao = np.hypot(extensao[('rx', 'max')] - extensao[('rx', 'min')],
                         extensao[('ry', 'max')] - extensao[('ry', 'min')])
    dispersao.name = 'chave_dispersao'

    log_a_conciliado = (log_a.map(lambda n: mapa_logradouros.get(n, n))
                        if mapa_logradouros else log_a)

    alvo = pd.DataFrame({
        'log': log_a_conciliado.values,
        'num': num_a.values,
        'ax': gdf_alvo.geometry.x.values,
        'ay': gdf_alvo.geometry.y.values,
    }, index=gdf_alvo.index).dropna(subset=['log', 'num'])

    par = alvo.reset_index(names='_idx').merge(ref, on=['log', 'num'], how='inner')
    par['d'] = np.hypot(par['ax'] - par['rx'], par['ay'] - par['ry'])
    melhor = par.loc[par.groupby('_idx')['d'].idxmin()].set_index('_idx')

    out = pd.DataFrame(index=gdf_alvo.index)
    out['dist_identidade'] = melhor['d'].reindex(gdf_alvo.index)
    out['ref_x'] = melhor['rx'].reindex(gdf_alvo.index)
    out['ref_y'] = melhor['ry'].reindex(gdf_alvo.index)
    disp_por_par = pd.Series(
        melhor.set_index(['log', 'num']).index.map(dispersao).to_numpy(),
        index=melhor.index, dtype=float,
    )
    out['chave_dispersao'] = disp_por_par.reindex(gdf_alvo.index)
    out['chave_ambigua'] = out['chave_dispersao'] > dispersao_ambigua_m
    out['pareado_identidade'] = out['dist_identidade'].notna()
    return out
