"""
ETL — Processamento das camadas de contexto BHMap.

Converte shapefiles/CSV brutos em GeoParquets limpos em data/processed/.

Outputs gerados:
  edificacao.parquet          — polígonos de edificações (PAV_EST + altitude MDT + rugosidade)
  area_risco.parquet          — risco inundação + escorregamento unificados (TIPO_RISCO)
  ivs.parquet                 — índice de vulnerabilidade saúde por setor (+ IVS_SCORE ordinal)
  lote_ctm.parquet            — lotes CTM joined com tipologia de uso/morfologia
  bairro_popular.parquet      — bairros populares com dados populacionais (POP_DOMIC_2022)
  cadastro_units.parquet      — unidades imobiliárias (sem geometria, join via NULOTCTM)
  cadastro_lotes.parquet      — lotes agregados com geometria + atributos fiscais/infra
  via_classifica.parquet      — classificação viária + hierarquia ordinal
  declividade.parquet         — declividade por trecho de logradouro (mediana, desvpad, classe)
  zoneamento.parquet          — zoneamento urbanístico (SIGLA_TIPO, classe social, flag AEIS/ZEIS)
  atividade_economica.parquet — pontos de CNPJ com CNAE (geometria + 3 atributos essenciais)
  setor_censitario.parquet    — setores censitários 2022 com população e densidade
  vila_favela.parquet         — assentamentos informais com tipo e plano urbanístico
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import from_wkt

from src import config

from rich.console import Console
console = Console()

CTX  = config.CONTEXT_DIR
OUT  = config.PROCESSED_DIR

IND_COLS = [
    "IND_MEIO_FIO", "IND_PAVIMENTACAO", "IND_ARBORIZACAO",
    "IND_GALERIA_PLUVIAL", "IND_ILUMINACAO_PUBLICA",
    "IND_REDE_ESGOTO", "IND_REDE_AGUA", "IND_REDE_TELEFONICA",
]

PADRAO_MAP = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "TE": np.nan}

IVS_MAP = {"Baixo": 1, "Médio": 2, "Elevado": 3, "Muito Elevado": 4}

# Hierarquia ordinal de classe viária (1=menor acesso → 6=maior conectividade)
VIA_HIERARQUIA_MAP = {
    "VIA DE PEDESTRES":    1,
    "MISTA":               2,
    "VIA SEM CLASSIFICACAO": 2,
    "LOCAL":               3,
    "COLETORA":            4,
    "ARTERIAL":            5,
    "LIGACAO REGIONAL":    6,
}

# Hierarquia ordinal de tipo de logradouro
VIA_TIPO_HIERARQUIA_MAP = {
    "BEC": 1, "VDP": 1, "PDC": 1,       # beco / via de pedestre
    "TRV": 2, "ALA": 2, "PCA": 2,       # travessa / ala / praça
    "RUA": 3, "TRE": 3, "LRG": 3,       # rua padrão
    "AVE": 4, "VIA": 4, "ROD": 4,       # avenida / rodovia
}

# Classes de declividade (%)
DECLIV_BINS   = [0, 5, 15, 30, 200]
DECLIV_LABELS = ["plano", "ondulado", "forte", "muito_forte"]

# Classificação simplificada do zoneamento
ZONA_CLASSE_MAP = {
    "AEIS_1": "INTERESSE_SOCIAL", "AEIS_2": "INTERESSE_SOCIAL",
    "ZEIS-1": "INTERESSE_SOCIAL", "ZEIS-2": "INTERESSE_SOCIAL",
    "PA-1":   "PARCELAMENTO",     "PA-2": "PARCELAMENTO", "PA-3": "PARCELAMENTO",
    "AGEUC":  "EQUIPAMENTO",      "AGEE": "EQUIPAMENTO",
    "OM-1":   "OPERACAO_MISTA",   "OM-2": "OPERACAO_MISTA",
    "OM-3":   "OPERACAO_MISTA",   "OM-4": "OPERACAO_MISTA",
    "OP-1":   "OPERACAO_RES",     "OP-2": "OPERACAO_RES", "OP-3": "OPERACAO_RES",
    "CR":     "CENTRO_REGIONAL",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. EDIFICACAO (agora inclui altitude MDT e rugosidade do terreno)
# ─────────────────────────────────────────────────────────────────────────────
def process_edificacao():
    print("[1/13] EDIFICACAO ...")
    gdf = gpd.read_file(CTX / "EDIFICACAO" / "EDIFICACAO.shp")

    gdf["ALTURA_CAL"] = gdf["ALTURA_CAL"].clip(lower=0)
    gdf["ALTURA_EST"] = gdf["ALTURA_EST"].clip(lower=0)
    gdf["PAV_EST"]    = (gdf["ALTURA_EST"] / 3.0).clip(lower=1).round().astype("int16")

    # Altitude do terreno (MDT) e rugosidade topográfica
    if "MEDIA_MDT" in gdf.columns:
        gdf["ALTITUDE_MDT"] = gdf["MEDIA_MDT"].astype("float32")
    if "DESVIO_PAD" in gdf.columns:
        # DESVIO_PAD = desvio padrão da altitude MDT dentro do polígono → proxy de inclinação
        gdf["RUGOSIDADE_MDT"] = gdf["DESVIO_PAD"].astype("float32")
    if "COTA_MIN_M" in gdf.columns:
        gdf["COTA_MIN_MDT"] = gdf["COTA_MIN_M"].astype("float32")

    if "OBSERVACAO" in gdf.columns:
        obs_upper = gdf["OBSERVACAO"].astype(str).str.upper()
        gdf["FLAG_EM_CONSTRUCAO"]    = obs_upper.str.contains("CONSTRU",  na=False).astype("int8")
        gdf["FLAG_ALTURA_IMPRECISA"] = obs_upper.str.contains("IMPRECIS", na=False).astype("int8")
    else:
        gdf["FLAG_EM_CONSTRUCAO"]    = np.int8(0)
        gdf["FLAG_ALTURA_IMPRECISA"] = np.int8(0)

    keep = ["ID_EDIF", "ID_LOTE_CT", "AREA", "ALTURA_CAL", "ALTURA_EST", "PAV_EST",
            "ALTITUDE_MDT", "RUGOSIDADE_MDT", "COTA_MIN_MDT",
            "FLAG_EM_CONSTRUCAO", "FLAG_ALTURA_IMPRECISA", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    out = OUT / "edificacao.parquet"
    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} edificações  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. AREA_RISCO
# ─────────────────────────────────────────────────────────────────────────────
def process_area_risco():
    print("[2/13] AREA_RISCO ...")
    ri = gpd.read_file(CTX / "AREA_RISCO_INUNDACAO"      / "AREA_RISCO_INUNDACAO.shp")[["geometry"]]
    re = gpd.read_file(CTX / "AREA_RISCO_ESCORREGAMENTO" / "AREA_RISCO_ESCORREGAMENTO.shp")[["geometry"]]
    ri["TIPO_RISCO"] = "INUNDACAO"
    re["TIPO_RISCO"] = "ESCORREGAMENTO"

    risco = gpd.GeoDataFrame(
        pd.concat([ri, re], ignore_index=True), geometry="geometry", crs=ri.crs
    ).dissolve(by="TIPO_RISCO").reset_index()

    out = OUT / "area_risco.parquet"
    risco.to_parquet(out)
    print(f"   -> {out.name}  {len(risco)} tipos  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 3. IVS
# ─────────────────────────────────────────────────────────────────────────────
def process_ivs():
    print("[3/13] IVS_INDICE_VULNERAB_SAUDE ...")
    gdf = gpd.read_file(CTX / "IVS_INDICE_VULNERAB_SAUDE" / "IVS_INDICE_VULNERAB_SAUDE.shp")
    gdf = gdf.rename(columns={"COD_SETOR_": "COD_SETOR", "POPULACAO_": "POPULACAO",
                               "ID_SETOR_C": "ID_SETOR_CTM"})
    gdf["IVS_SCORE"]        = gdf["IVS_2012"].map(IVS_MAP).astype("float32")
    gdf["FLAG_NAO_AVALIADO"] = gdf["IVS_SCORE"].isna().astype("int8")

    keep = ["COD_SETOR", "ID_SETOR_CTM", "POPULACAO", "POPFEM", "POPMASC",
            "IVS_2012", "IVS_SCORE", "FLAG_NAO_AVALIADO", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    out = OUT / "ivs.parquet"
    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} setores  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 4. LOTE_CTM + TIPOLOGIA_USO
# ─────────────────────────────────────────────────────────────────────────────
def process_lote_ctm():
    print("[4/13] LOTE_CTM + TIPOLOGIA_USO_LOTE ...")
    lote = gpd.read_file(CTX / "LOTE_CTM" / "LOTE_CTM.shp")
    lote = lote.rename(columns={"ID_QUADRA_": "ID_QUADRA_CTM"})

    tip = gpd.read_file(CTX / "TIPOLOGIA_USO_OCUPACAO_LOTE_2022" / "TIPOLOGIA_USO_OCUPACAO_LOTE_2022.shp")
    tip_attrs = (
        tip[["NULOTCTM", "TIPOLOGIA_", "TIPOLOGIA0", "MORFOLOGIA"]]
        .rename(columns={"TIPOLOGIA_": "TIPOLOGIA_BROAD", "TIPOLOGIA0": "TIPOLOGIA_DETALHE"})
    )
    lote = lote.merge(tip_attrs, on="NULOTCTM", how="left")
    for col in ["TIPOLOGIA_BROAD", "TIPOLOGIA_DETALHE", "MORFOLOGIA"]:
        lote[col] = lote[col].fillna("SEM CLASSIFICACAO")

    out = OUT / "lote_ctm.parquet"
    lote.to_parquet(out)
    n_tip = (lote["TIPOLOGIA_BROAD"] != "SEM CLASSIFICACAO").sum()
    print(f"   -> {out.name}  {len(lote):,} lotes  ({n_tip:,} tipificados)  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 5. BAIRRO_POPULAR + POP_DOMIC_2022
# ─────────────────────────────────────────────────────────────────────────────
def process_bairro_popular():
    print("[5/13] BAIRRO_POPULAR + POP_DOMIC_2022 ...")
    bp  = gpd.read_file(CTX / "BAIRRO_POPULAR" / "BAIRRO_POPULAR.shp")
    pop = gpd.read_file(CTX / "POP_DOMIC_BAIRRO_2022" / "POP_DOMIC_BAIRRO_2022.shp")

    bp["COD_BAIRRO"]  = bp["CODIGO"].astype("Int64")
    pop["COD_BAIRRO"] = pop["NUM_BAIRRO"].astype("Int64")

    merged = bp.merge(pop[["COD_BAIRRO", "POPULACAO", "DOMICILIOS", "DENSIDADE_"]],
                      on="COD_BAIRRO", how="left")
    merged = merged.rename(columns={"NOME": "NOME_BAIRRO", "DENSIDADE_": "DENS_HAB_KM2"})

    keep = ["COD_BAIRRO", "NOME_BAIRRO", "AREA_KM2", "POPULACAO", "DOMICILIOS",
            "DENS_HAB_KM2", "geometry"]
    merged = merged[[c for c in keep if c in merged.columns]]

    out = OUT / "bairro_popular.parquet"
    merged.to_parquet(out)
    print(f"   -> {out.name}  {len(merged):,} bairros  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 6 + 7. CADASTRO_IMOBILIARIO
# ─────────────────────────────────────────────────────────────────────────────
def process_cadastro():
    print("[6/13] CADASTRO_IMOBILIARIO — lendo CSV (767 MB) ...")
    df = pd.read_csv(CTX / "CADASTRO_IMOBILIARIO.csv", encoding="utf-8", low_memory=False)
    print(f"   {len(df):,} unidades  {df['NULOTCTM'].nunique():,} lotes únicos")

    for c in IND_COLS:
        if c in df.columns:
            df[c] = (df[c].astype(str).str.strip().str.upper() == "SIM").astype("int8")

    avail_ind = [c for c in IND_COLS if c in df.columns]
    df["INFRA_SCORE"]  = df[avail_ind].sum(axis=1).astype("int8")
    df["PADRAO_SCORE"] = df["PADRAO_ACABAMENTO"].map(PADRAO_MAP).astype("float32")

    df["ANO_CONSTRUCAO"] = pd.to_numeric(df["ANO_CONSTRUCAO"], errors="coerce")
    df.loc[(df["ANO_CONSTRUCAO"] < 1700) | (df["ANO_CONSTRUCAO"] > 2025), "ANO_CONSTRUCAO"] = np.nan
    df["ANO_CONSTRUCAO"] = df["ANO_CONSTRUCAO"].astype("Int16")

    df["FLAG_TERRITORIAL"] = (df["TIPO_OCUPACAO"].astype(str).str.upper() == "TERRITORIAL").astype("int8")
    df["FLAG_LOTE_VAGO"]   = (df["TIPO_CONSTRUTIVO"].astype(str).str.upper() == "LOTE VAGO").astype("int8")

    print("[7/13] Salvando cadastro_units.parquet ...")
    unit_cols = (
        ["FID", "INDICE_CADASTRAL", "NULOTCTM", "ZONEAMENTO_PVIPTU", "TIPO_CONSTRUTIVO",
         "TIPO_OCUPACAO", "PADRAO_ACABAMENTO", "PADRAO_SCORE", "QUANTIDADE_ECONOMIAS",
         "AREA_TERRENO", "AREA_CONSTRUCAO", "FRACAO_IDEAL", "ZONA_HOMOGENEA", "TIPOLOGIA",
         "ANO_CONSTRUCAO", "INFRA_SCORE", "NOME_LOGRADOURO", "NUMERO_IMOVEL", "CEP",
         "FLAG_TERRITORIAL", "FLAG_LOTE_VAGO"] + avail_ind
    )
    unit_df = df[[c for c in unit_cols if c in df.columns]].copy()
    out_units = OUT / "cadastro_units.parquet"
    unit_df.to_parquet(out_units, index=False)
    print(f"   -> {out_units.name}  {len(unit_df):,} unidades  ({out_units.stat().st_size/1e6:.1f} MB)")

    print("[8/13] Agregando lotes com geometria ...")

    def _mode_or_nan(s):
        m = s.dropna()
        return m.mode().iloc[0] if len(m) > 0 else np.nan

    lot_agg = df.groupby("NULOTCTM", sort=False).agg(
        TIPO_OCUPACAO     =("TIPO_OCUPACAO",      _mode_or_nan),
        TIPO_CONSTRUTIVO  =("TIPO_CONSTRUTIVO",   _mode_or_nan),
        TIPOLOGIA         =("TIPOLOGIA",          _mode_or_nan),
        PADRAO_SCORE      =("PADRAO_SCORE",       "median"),
        QTDE_ECONOMIAS    =("QUANTIDADE_ECONOMIAS", "sum"),
        AREA_CONSTR_TOTAL =("AREA_CONSTRUCAO",    "sum"),
        AREA_TERRENO      =("AREA_TERRENO",       "first"),
        ANO_MIN           =("ANO_CONSTRUCAO",     "min"),
        INFRA_SCORE       =("INFRA_SCORE",        "first"),
        ZONA_HOMOGENEA    =("ZONA_HOMOGENEA",     "first"),
        ZONEAMENTO_PVIPTU =("ZONEAMENTO_PVIPTU",  "first"),
        FLAG_TERRITORIAL  =("FLAG_TERRITORIAL",   "max"),
        FLAG_LOTE_VAGO    =("FLAG_LOTE_VAGO",     "max"),
        **{c: (c, "first") for c in avail_ind},
    ).reset_index()

    lot_geom = df.groupby("NULOTCTM", sort=False)["GEOMETRIA"].first().reset_index()
    print(f"   Parseando {len(lot_geom):,} geometrias WKT ...")
    lot_geom["geometry"] = from_wkt(lot_geom["GEOMETRIA"].values)

    lot_gdf = gpd.GeoDataFrame(
        lot_agg.merge(lot_geom[["NULOTCTM", "geometry"]], on="NULOTCTM", how="left"),
        geometry="geometry", crs="EPSG:31983",
    )

    out_lotes = OUT / "cadastro_lotes.parquet"
    lot_gdf.to_parquet(out_lotes)
    print(f"   -> {out_lotes.name}  {len(lot_gdf):,} lotes  ({out_lotes.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 8. CLASSIFICACAO_VIARIA
# ─────────────────────────────────────────────────────────────────────────────
def process_via_classifica():
    print("[9/13] CLASSIFICACAO_VIARIA ...")
    out = OUT / "via_classifica.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe")
        return

    gdf = gpd.read_file(config.CLASSIFICACAO_VIARIA_SHP)
    gdf = gdf.rename(columns={"CLASSIFICA": "VIA_CLASSIFICA", "TP_LOG": "VIA_TIPO_LOG",
                               "DESCRICAO_": "VIA_LARGURA_DESC"})

    # Hierarquia ordinal da classe viária (1=pedestres → 6=ligação regional)
    gdf["VIA_HIERARQUIA"] = (
        gdf["VIA_CLASSIFICA"].str.upper().str.strip()
        .map(VIA_HIERARQUIA_MAP)
        .fillna(2)
        .astype("int8")
    )

    # Hierarquia ordinal do tipo de logradouro
    gdf["VIA_TIPO_ORD"] = (
        gdf["VIA_TIPO_LOG"].str.upper().str.strip()
        .map(VIA_TIPO_HIERARQUIA_MAP)
        .fillna(2)
        .astype("int8")
    )

    # Largura ordinal (1=estreita, 2=média, 3=larga)
    def _largura_ord(desc):
        if pd.isna(desc): return np.nan
        d = str(desc).upper()
        if "< 10" in d:  return 1
        if ">= 15" in d: return 3
        return 2

    gdf["VIA_LARGURA_ORD"] = gdf["VIA_LARGURA_DESC"].apply(_largura_ord).astype("float32")
    gdf["FLAG_BECO"]        = (gdf["VIA_TIPO_LOG"].str.upper() == "BEC").astype("int8")

    keep = ["VIA_CLASSIFICA", "VIA_TIPO_LOG", "VIA_LARGURA_DESC",
            "VIA_HIERARQUIA", "VIA_TIPO_ORD", "VIA_LARGURA_ORD", "FLAG_BECO", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} trechos  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 9. DECLIVIDADE_TRECHO_LOGRADOURO
# ─────────────────────────────────────────────────────────────────────────────
def process_declividade():
    print("[10/13] DECLIVIDADE_TRECHO_LOGRADOURO ...")
    out = OUT / "declividade.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe")
        return

    gdf = gpd.read_file(config.DECLIVIDADE_SHP)

    # Campos truncados pelo formato DBF (10 chars):
    # DECLIVIDAD = min, DECLIVIDA0 = max, DECLIVIDA1 = média, MEDIANA = mediana
    rename = {}
    if "DECLIVIDAD" in gdf.columns: rename["DECLIVIDAD"] = "DECLIV_MIN"
    if "DECLIVIDA0" in gdf.columns: rename["DECLIVIDA0"] = "DECLIV_MAX"
    if "DECLIVIDA1" in gdf.columns: rename["DECLIVIDA1"] = "DECLIV_MEDIA"
    if "MEDIANA"    in gdf.columns: rename["MEDIANA"]    = "DECLIV_MEDIANA"
    if "DESVIO_PAD" in gdf.columns: rename["DESVIO_PAD"] = "DECLIV_DESVPAD"
    gdf = gdf.rename(columns=rename)

    for c in ["DECLIV_MIN","DECLIV_MAX","DECLIV_MEDIA","DECLIV_MEDIANA","DECLIV_DESVPAD"]:
        if c in gdf.columns:
            gdf[c] = gdf[c].astype("float32")

    # Classe de declividade pela mediana
    if "DECLIV_MEDIANA" in gdf.columns:
        gdf["DECLIV_CLASSE"] = pd.cut(
            gdf["DECLIV_MEDIANA"],
            bins=DECLIV_BINS, labels=DECLIV_LABELS, right=False
        ).astype(str)
        gdf.loc[gdf["DECLIV_MEDIANA"].isna(), "DECLIV_CLASSE"] = np.nan

    keep = ["NOME_LOGRA", "DECLIV_MIN", "DECLIV_MAX", "DECLIV_MEDIA",
            "DECLIV_MEDIANA", "DECLIV_DESVPAD", "DECLIV_CLASSE", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} trechos  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 10. ZONEAMENTO
# ─────────────────────────────────────────────────────────────────────────────
def process_zoneamento():
    print("[11/13] ZONEAMENTO_11181 ...")
    out = OUT / "zoneamento.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe")
        return

    gdf = gpd.read_file(config.ZONEAMENTO_SHP)
    gdf = gdf.rename(columns={"DESC_TIPO_": "ZONA_DESC", "SIGLA_TIPO": "ZONA_TIPO"})

    gdf["ZONA_CLASSE"]      = gdf["ZONA_TIPO"].map(ZONA_CLASSE_MAP).fillna("OUTRO")
    gdf["FLAG_ZONA_SOCIAL"] = gdf["ZONA_TIPO"].str.upper().str.contains(
        "AEIS|ZEIS", na=False
    ).astype("int8")

    keep = ["ZONA_TIPO", "ZONA_DESC", "ZONA_CLASSE", "FLAG_ZONA_SOCIAL", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} zonas  ({gdf['ZONA_TIPO'].value_counts().to_dict()})  "
          f"({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 11. ATIVIDADE_ECONOMICA (arquivo grande — ler só colunas essenciais)
# ─────────────────────────────────────────────────────────────────────────────
def process_atividade_economica():
    print("[12/13] ATIVIDADE_ECONOMICA (arquivo grande — pode demorar ~5 min) ...")
    out = OUT / "atividade_economica.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe ({out.stat().st_size/1e6:.1f} MB)")
        return

    gdf = gpd.read_file(config.ATIVIDADE_ECONOMICA_SHP)
    print(f"   Lidos {len(gdf):,} estabelecimentos")

    # Manter apenas o necessário para análise espacial
    keep = ["CNAE_PRINC", "PORTE_EMPR", "TIPO_UNIDA", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]].copy()

    # Divisão CNAE (2 dígitos) — proxy de setor econômico
    gdf["CNAE_DIV"] = gdf["CNAE_PRINC"].astype(str).str[:2]

    # Flag: é unidade produtiva (não apenas escritório administrativo)
    if "TIPO_UNIDA" in gdf.columns:
        gdf["FLAG_UNID_PRODUTIVA"] = (
            gdf["TIPO_UNIDA"].str.upper().str.contains("PRODUTIVA", na=False)
        ).astype("int8")

    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} estabelecimentos  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 12. SETOR_CENSITARIO_2022 (com população e densidade domiciliar)
# ─────────────────────────────────────────────────────────────────────────────
def process_setor_censitario():
    print("[13/13] SETOR_CENSITARIO_2022 ...")
    out = OUT / "setor_censitario.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe")
        return

    gdf = gpd.read_file(config.SETOR_CENSITARIO_SHP)
    gdf = gdf.rename(columns={
        "COD_SETOR":   "COD_SETOR",
        "TIPO_SITUA":  "TIPO_SITUACAO",
        "NOME_SUBDI":  "NOME_SUBDISTR",
        "REGIONAL_C":  "REGIONAL_CTM",
        "BAIRRO_CON":  "BAIRRO_NOME",
        "QT_TOT_PES":  "POP_SETOR",
        "QT_TOT_DOM":  "DOM_SETOR",
        "TGC_CONSID":  "TGC",
    })

    # Área em km² e densidade domiciliar
    if gdf.crs is None or gdf.crs.to_epsg() != 31983:
        gdf = gdf.to_crs("EPSG:31983")
    gdf["AREA_KM2_SETOR"]  = (gdf.geometry.area / 1e6).astype("float32")
    gdf["DENS_DOM_KM2"]    = (gdf["DOM_SETOR"] / gdf["AREA_KM2_SETOR"].replace(0, np.nan)).astype("float32")
    gdf["DENS_POP_KM2"]    = (gdf["POP_SETOR"] / gdf["AREA_KM2_SETOR"].replace(0, np.nan)).astype("float32")

    keep = ["COD_SETOR", "TIPO_SITUACAO", "NOME_SUBDISTR", "REGIONAL_CTM", "BAIRRO_NOME",
            "POP_SETOR", "DOM_SETOR", "AREA_KM2_SETOR", "DENS_DOM_KM2", "DENS_POP_KM2", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    gdf.to_parquet(out)
    print(f"   -> {out.name}  {len(gdf):,} setores  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# 13. VILA_FAVELA (enriquecida com tipo e plano urbanístico)
# ─────────────────────────────────────────────────────────────────────────────
def process_vila_favela():
    print("[13b/13] VILA_FAVELA (enriquecida) ...")
    out = OUT / "vila_favela.parquet"
    if out.exists():
        print(f"   [SKIP] {out.name} já existe")
        return

    gdf = gpd.read_file(config.VILAS_FAVELAS_SHP)
    gdf = gdf.rename(columns={
        "NOME_LOCAL": "NOME_ASSENTAMENTO",
        "DESC_LOCAL": "TIPO_ASSENTAMENTO",
        "PLANO_URBA": "TEM_PLANO_URBANO",
        "QTDE_DOMIC": "QTD_DOMICILIOS",
        "QTDE_ESTAB": "QTD_ESTAB",
        "QTDE_POPUL": "QTD_POPULACAO",
    })

    # Simplifica tipo de assentamento
    if "TIPO_ASSENTAMENTO" in gdf.columns:
        gdf["TIPO_ASSENTAMENTO"] = (
            gdf["TIPO_ASSENTAMENTO"]
            .str.upper().str.strip()
            .str.replace("LOTEAMENTO PÚBLICO DE INTERESSE SOCIAL", "LOTEAMENTO_SOCIAL", regex=False)
            .str.replace("VILA / FAVELA", "VILA_FAVELA", regex=False)
            .fillna("NAO_CLASSIFICADO")
        )

    # Plano urbanístico como flag ordinal
    if "TEM_PLANO_URBANO" in gdf.columns:
        plano_map = {"Sim": 2, "Em andamento": 1, "Não": 0}
        gdf["PLANO_URBANO_ORD"] = gdf["TEM_PLANO_URBANO"].map(plano_map).fillna(0).astype("int8")

    keep = ["NOME_ASSENTAMENTO", "TIPO_ASSENTAMENTO", "TEM_PLANO_URBANO", "PLANO_URBANO_ORD",
            "QTD_DOMICILIOS", "QTD_ESTAB", "QTD_POPULACAO", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    gdf.to_parquet(out)
    n_vf  = (gdf["TIPO_ASSENTAMENTO"] == "VILA_FAVELA").sum() if "TIPO_ASSENTAMENTO" in gdf.columns else "?"
    n_lot = (gdf["TIPO_ASSENTAMENTO"] == "LOTEAMENTO_SOCIAL").sum() if "TIPO_ASSENTAMENTO" in gdf.columns else "?"
    print(f"   -> {out.name}  {len(gdf):,} assentamentos  "
          f"(Vila/Favela={n_vf}, Loteamento={n_lot})  ({out.stat().st_size/1e6:.1f} MB)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    console.rule("[bold]ETL — Camadas de Contexto BHMap")
    process_edificacao()
    process_area_risco()
    process_ivs()
    process_lote_ctm()
    process_bairro_popular()
    process_cadastro()
    process_via_classifica()
    process_declividade()
    process_zoneamento()
    process_atividade_economica()
    process_setor_censitario()
    process_vila_favela()
    print(f"\n  Parquets gerados em {OUT}")
    console.rule("[bold green]ETL concluído")
