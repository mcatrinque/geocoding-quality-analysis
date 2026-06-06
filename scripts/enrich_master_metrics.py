"""
scripts/enrich_master_metrics.py

Enriquece cnefe_master_metrics_base.parquet com variáveis contextuais de 13 camadas
BHMap, gerando cnefe_master_metrics.parquet (~100 colunas).

Joins realizados (por cobertura esperada decrescente):
  1.  IVS          (5.166 setores)    → ~98%  → IVS_SCORE, IVS_NORM, IVS_ALTO
  2.  AREA_RISCO   (2 tipos)          → ~15%  → em_risco, TIPO_RISCO, em_inundacao, em_escorregamento
  3.  LOTE_CTM     (~365k lotes)      → ~39%  → TIPOLOGIA_BROAD, TIPOLOGIA_DETALHE, MORFOLOGIA
  4.  CADASTRO_LOTES (~306k lotes)    → ~34%  → INFRA_SCORE, PADRAO_SCORE, FLAGS,
                                               IND_GALERIA_PLUVIAL, IND_PAVIMENTACAO,
                                               IND_REDE_ESGOTO, ANO_MIN_CONSTRUCAO,
                                               AREA_TERRENO, AREA_CONSTR_TOTAL
  5.  EDIFICACAO   (~739k polígonos)  → ~60%  → PAV_EST, ALTITUDE_MDT, RUGOSIDADE_MDT (≤30m)
  6.  VIA_CLASSIFICA (~54k trechos)   → ~95%  → VIA_CLASSIFICA, VIA_HIERARQUIA, VIA_TIPO_LOG,
                                               VIA_LARGURA_ORD, FLAG_BECO
  7.  DECLIVIDADE  (~13k trechos)     → ~80%  → DECLIV_MEDIANA, DECLIV_DESVPAD, DECLIV_CLASSE
  8.  ZONEAMENTO   (~1.7k polígonos)  → ~30%  → ZONA_TIPO, ZONA_CLASSE, FLAG_ZONA_SOCIAL
  9.  ATIVIDADE_ECON (pontos CNPJ)    → setor → DENS_ATIV_ECON_KM2
                                      → COD_ESPECIE 6/7 → FLAG_ESTAB_VALIDADO, DIST_ATIV_MIN
  10. SETOR_CENSITARIO (~5k setores)  → ~98%  → POP_SETOR, DOM_SETOR, DENS_DOM_KM2
  11. VILA_FAVELA  (218 polígonos)    → ~5%   → em_favela, TIPO_ASSENTAMENTO,
                                               TEM_PLANO_URBANO, PLANO_URBANO_ORD
  12. Flags internas (sem join)       → 100%  → FLAG_NUMERO_INVALIDO, FLAG_COMPLEMENTO,
                                               FLAG_ESTABELECIMENTO, VIA_SIGLA_BH

Variáveis derivadas:
  - TIPOLOGIA_CLASSE    : versão simplificada de TIPOLOGIA_BROAD (6 classes)
  - PADRAO_NORM / INFRA_NORM / IVS_NORM / PAV_LOG
  - VULNERAB_COMPOSTA   : IVS_SCORE ≥ 3 AND em_risco
  - CONTEXTO_FORMAL     : FLAG_TERRITORIAL=0 AND INFRA_SCORE ≥ 4
  - IVS_ALTO / PAV_TIPO
  - IDADE_IMOVEL        : 2022 - ANO_MIN_CONSTRUCAO
  - TAXA_OCUPACAO       : AREA_CONSTR_TOTAL / AREA_TERRENO
  - ALTITUDE_CLASSE     : faixas de altitude (baixa/media/alta/muito_alta)
"""

import sys, warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import geopandas as gpd
from src import config

from rich.console import Console
console = Console()

CRS  = config.TARGET_CRS
OUT  = config.PROCESSED_DIR
PROC = config.PROCESSED_DIR

TIPOLOGIA_CLASSE_MAP = {
    "RESIDENCIAL UNIFAMILIAR":    "RESIDENCIAL",
    "RESIDENCIAL MULTIFAMILIAR":  "RESIDENCIAL",
    "RESIDENCIAL":                "RESIDENCIAL",
    "COMERCIAL":                  "COMERCIAL",
    "SERVICOS":                   "COMERCIAL",
    "SERVIÇOS":                   "COMERCIAL",
    "MISTO RESIDENCIAL/COMERCIAL":"MISTO",
    "MISTO":                      "MISTO",
    "USO MISTO":                  "MISTO",
    "INDUSTRIAL":                 "INDUSTRIAL",
    "ESPECIAL":                   "ESPECIAL",
    "INSTITUCIONAL":              "ESPECIAL",
    "AREA VERDE":                 "ESPECIAL",
    "ÁREA VERDE":                 "ESPECIAL",
    "SEM CLASSIFICACAO":          "SEM_CLASSIF",
}

ALTITUDE_BINS   = [0, 800, 900, 1000, 5000]
ALTITUDE_LABELS = ["baixa", "media", "alta", "muito_alta"]


def _sjoin_dedup(left, right, how="left", predicate="within"):
    joined = gpd.sjoin(left, right, how=how, predicate=predicate)
    return joined[~joined.index.duplicated(keep="first")]


def load_base():
    print("[BASE] Carregando cnefe_master_metrics_base.parquet ...")
    gdf = gpd.read_parquet(PROC / "cnefe_master_metrics_base.parquet")
    if gdf.crs is None or gdf.crs.to_epsg() != 31983:
        gdf = gdf.to_crs(CRS)
    print(f"  {len(gdf):,} registros  {len(gdf.columns)} colunas  CRS={gdf.crs.to_epsg()}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 1. IVS
# ─────────────────────────────────────────────────────────────────────────────
def join_ivs(gdf):
    print("[1/12] IVS ...")
    ivs = gpd.read_parquet(PROC / "ivs.parquet").to_crs(CRS)
    keep = [c for c in ["IVS_SCORE", "IVS_2012", "FLAG_NAO_AVALIADO", "geometry"] if c in ivs.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], ivs[keep], predicate="within")
    for col in ["IVS_SCORE", "IVS_2012", "FLAG_NAO_AVALIADO"]:
        if col in joined.columns:
            gdf[col] = joined[col]
    pct = gdf["IVS_SCORE"].notna().mean() * 100
    print(f"  Cobertura IVS: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 2. AREA_RISCO (granular: inundação e escorregamento separados)
# ─────────────────────────────────────────────────────────────────────────────
def join_area_risco(gdf):
    print("[2/12] AREA_RISCO ...")
    risco = gpd.read_parquet(PROC / "area_risco.parquet").to_crs(CRS)
    joined = _sjoin_dedup(gdf[["geometry"]], risco[["TIPO_RISCO", "geometry"]], predicate="within")
    gdf["TIPO_RISCO"]        = joined["TIPO_RISCO"]
    gdf["em_risco"]          = gdf["TIPO_RISCO"].notna().astype("int8")
    gdf["em_inundacao"]      = (gdf["TIPO_RISCO"] == "INUNDACAO").astype("int8")
    gdf["em_escorregamento"] = (gdf["TIPO_RISCO"] == "ESCORREGAMENTO").astype("int8")
    pct = gdf["em_risco"].mean() * 100
    print(f"  em_risco: {pct:.1f}%  "
          f"(inundação={gdf['em_inundacao'].sum():,}  escorr.={gdf['em_escorregamento'].sum():,})")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 3. LOTE_CTM (tipologia + morfologia)
# ─────────────────────────────────────────────────────────────────────────────
def join_lote_ctm(gdf):
    print("[3/12] LOTE_CTM ...")
    lote = gpd.read_parquet(PROC / "lote_ctm.parquet").to_crs(CRS)
    keep_cols = [c for c in ["NULOTCTM", "TIPOLOGIA_BROAD", "TIPOLOGIA_DETALHE", "MORFOLOGIA", "geometry"]
                 if c in lote.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], lote[keep_cols], predicate="within")
    for col in ["NULOTCTM", "TIPOLOGIA_BROAD", "TIPOLOGIA_DETALHE", "MORFOLOGIA"]:
        if col in joined.columns:
            out_col = "NULOTCTM_CTM" if col == "NULOTCTM" else col
            gdf[out_col] = joined[col]
    if "TIPOLOGIA_BROAD" in gdf.columns:
        gdf["TIPOLOGIA_CLASSE"] = (
            gdf["TIPOLOGIA_BROAD"].str.upper().str.strip()
            .map(TIPOLOGIA_CLASSE_MAP).fillna("SEM_CLASSIF")
        )
    pct = gdf.get("TIPOLOGIA_BROAD", pd.Series(dtype=str)).notna().mean() * 100
    print(f"  Cobertura TIPOLOGIA_BROAD: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 4. CADASTRO_LOTES (infra individual + padrão + flags + área + idade)
# ─────────────────────────────────────────────────────────────────────────────
def join_cadastro(gdf):
    print("[4/12] CADASTRO_LOTES ...")
    cad = gpd.read_parquet(PROC / "cadastro_lotes.parquet").to_crs(CRS)

    want = ["INFRA_SCORE", "PADRAO_SCORE", "FLAG_TERRITORIAL", "FLAG_LOTE_VAGO",
            "TIPO_OCUPACAO", "TIPO_CONSTRUTIVO", "ZONA_HOMOGENEA", "ZONEAMENTO_PVIPTU",
            "QTDE_ECONOMIAS", "ANO_MIN", "AREA_TERRENO", "AREA_CONSTR_TOTAL",
            "IND_GALERIA_PLUVIAL", "IND_PAVIMENTACAO", "IND_REDE_ESGOTO",
            "IND_REDE_AGUA", "IND_ILUMINACAO_PUBLICA", "geometry"]
    keep_cols = [c for c in want if c in cad.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], cad[keep_cols], predicate="within")

    cad_cols = [c for c in keep_cols if c != "geometry"]
    for col in cad_cols:
        gdf[f"CAD_{col}"] = joined[col]

    # Renomear colunas principais sem prefixo
    for col in ["INFRA_SCORE", "PADRAO_SCORE", "FLAG_TERRITORIAL", "FLAG_LOTE_VAGO",
                "ZONA_HOMOGENEA", "TIPO_OCUPACAO", "AREA_TERRENO", "AREA_CONSTR_TOTAL",
                "IND_GALERIA_PLUVIAL", "IND_PAVIMENTACAO", "IND_REDE_ESGOTO",
                "IND_REDE_AGUA", "IND_ILUMINACAO_PUBLICA"]:
        cad_col = f"CAD_{col}"
        if cad_col in gdf.columns and col not in gdf.columns:
            gdf[col] = gdf[cad_col]
            gdf.drop(columns=[cad_col], inplace=True)

    # ANO_MIN → nome explícito
    if "CAD_ANO_MIN" in gdf.columns:
        gdf["ANO_MIN_CONSTRUCAO"] = gdf.pop("CAD_ANO_MIN")

    pct = gdf["INFRA_SCORE"].notna().mean() * 100
    print(f"  Cobertura INFRA_SCORE: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 5. EDIFICACAO (PAV_EST + altitude MDT + rugosidade)
# ─────────────────────────────────────────────────────────────────────────────
def join_edificacao(gdf):
    print("[5/12] EDIFICACAO (sjoin_nearest <=30m) ...")
    edif = gpd.read_parquet(PROC / "edificacao.parquet").to_crs(CRS)
    edif_ctr = edif.copy()
    edif_ctr["geometry"] = edif.geometry.centroid

    want = ["PAV_EST", "ALTITUDE_MDT", "RUGOSIDADE_MDT", "COTA_MIN_MDT", "AREA",
            "FLAG_EM_CONSTRUCAO", "FLAG_ALTURA_IMPRECISA", "geometry"]
    keep_cols = [c for c in want if c in edif_ctr.columns]

    joined = gpd.sjoin_nearest(
        gdf[["geometry"]], edif_ctr[keep_cols],
        how="left", max_distance=30.0, distance_col="_edif_dist",
    )
    joined = joined[~joined.index.duplicated(keep="first")]

    for col in [c for c in keep_cols if c != "geometry"]:
        if col in joined.columns:
            out_col = "AREA_EDIFICACAO" if col == "AREA" else col
            gdf[out_col] = joined[col]

    pct = gdf["PAV_EST"].notna().mean() * 100
    pct_alt = gdf.get("ALTITUDE_MDT", pd.Series()).notna().mean() * 100
    print(f"  Cobertura PAV_EST: {pct:.1f}%  |  ALTITUDE_MDT: {pct_alt:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLASSIFICACAO_VIARIA (sjoin_nearest ao trecho mais próximo)
# ─────────────────────────────────────────────────────────────────────────────
def join_via_classifica(gdf):
    print("[6/12] VIA_CLASSIFICA (sjoin_nearest) ...")
    via_path = PROC / "via_classifica.parquet"
    if not via_path.exists():
        print("  AVISO: via_classifica.parquet não encontrado — execute process_context_layers.py")
        return gdf

    via = gpd.read_parquet(via_path).to_crs(CRS)
    want = ["VIA_CLASSIFICA", "VIA_TIPO_LOG", "VIA_LARGURA_DESC",
            "VIA_HIERARQUIA", "VIA_TIPO_ORD", "VIA_LARGURA_ORD", "FLAG_BECO", "geometry"]
    keep_cols = [c for c in want if c in via.columns]

    joined = gpd.sjoin_nearest(
        gdf[["geometry"]], via[keep_cols],
        how="left", max_distance=150.0, distance_col="_via_dist",
    )
    joined = joined[~joined.index.duplicated(keep="first")]

    for col in [c for c in keep_cols if c != "geometry"]:
        if col in joined.columns:
            gdf[col] = joined[col]

    pct = gdf["VIA_CLASSIFICA"].notna().mean() * 100 if "VIA_CLASSIFICA" in gdf.columns else 0
    print(f"  Cobertura VIA_CLASSIFICA: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 7. DECLIVIDADE (sjoin_nearest ao trecho mais próximo)
# ─────────────────────────────────────────────────────────────────────────────
def join_declividade(gdf):
    print("[7/12] DECLIVIDADE (sjoin_nearest) ...")
    dec_path = PROC / "declividade.parquet"
    if not dec_path.exists():
        print("  AVISO: declividade.parquet não encontrado — execute process_context_layers.py")
        return gdf

    dec = gpd.read_parquet(dec_path).to_crs(CRS)
    want = ["DECLIV_MEDIANA", "DECLIV_MAX", "DECLIV_MEDIA", "DECLIV_DESVPAD",
            "DECLIV_CLASSE", "geometry"]
    keep_cols = [c for c in want if c in dec.columns]

    joined = gpd.sjoin_nearest(
        gdf[["geometry"]], dec[keep_cols],
        how="left", max_distance=200.0, distance_col="_dec_dist",
    )
    joined = joined[~joined.index.duplicated(keep="first")]

    for col in [c for c in keep_cols if c != "geometry"]:
        if col in joined.columns:
            gdf[col] = joined[col]

    pct = gdf["DECLIV_MEDIANA"].notna().mean() * 100 if "DECLIV_MEDIANA" in gdf.columns else 0
    print(f"  Cobertura DECLIV_MEDIANA: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 8. ZONEAMENTO (sjoin within)
# ─────────────────────────────────────────────────────────────────────────────
def join_zoneamento(gdf):
    print("[8/12] ZONEAMENTO ...")
    zon_path = PROC / "zoneamento.parquet"
    if not zon_path.exists():
        print("  AVISO: zoneamento.parquet não encontrado — execute process_context_layers.py")
        return gdf

    zon = gpd.read_parquet(zon_path).to_crs(CRS)
    want = ["ZONA_TIPO", "ZONA_CLASSE", "FLAG_ZONA_SOCIAL", "geometry"]
    keep_cols = [c for c in want if c in zon.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], zon[keep_cols], predicate="within")

    for col in [c for c in keep_cols if c != "geometry"]:
        if col in joined.columns:
            gdf[col] = joined[col]

    pct = gdf["ZONA_TIPO"].notna().mean() * 100 if "ZONA_TIPO" in gdf.columns else 0
    n_social = int(gdf.get("FLAG_ZONA_SOCIAL", pd.Series(0)).sum())
    print(f"  Cobertura ZONA_TIPO: {pct:.1f}%  |  FLAG_ZONA_SOCIAL=1: {n_social:,}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 9. ATIVIDADE_ECONOMICA
#    9a: densidade por setor censitário (todos os registros)
#    9b: validação de estabelecimentos (COD_ESPECIE ∈ {6,7})
# ─────────────────────────────────────────────────────────────────────────────
def join_atividade_economica(gdf):
    print("[9/12] ATIVIDADE_ECONOMICA ...")
    atv_path = PROC / "atividade_economica.parquet"
    sec_path = PROC / "setor_censitario.parquet"

    if not atv_path.exists():
        print("  AVISO: atividade_economica.parquet não encontrado — execute process_context_layers.py")
        return gdf

    atv = gpd.read_parquet(atv_path).to_crs(CRS)
    print(f"  {len(atv):,} estabelecimentos carregados")

    # 9a — Densidade de atividade econômica por setor censitário
    if sec_path.exists() and "COD_SETOR" in gdf.columns:
        sec = gpd.read_parquet(sec_path).to_crs(CRS)
        # Contar estabelecimentos por setor via sjoin
        atv_idx = gpd.sjoin(
            atv[["geometry"]],
            sec[["COD_SETOR", "AREA_KM2_SETOR", "geometry"]],
            how="left", predicate="within",
        ).dropna(subset=["COD_SETOR"])

        setor_count = atv_idx.groupby("COD_SETOR").size().rename("N_ATIV_ECON")
        setor_area  = sec.set_index("COD_SETOR")["AREA_KM2_SETOR"]
        setor_dens  = (setor_count / setor_area).rename("DENS_ATIV_ECON_KM2")

        # Merge de volta ao gdf via COD_SETOR
        cod_map = gdf["COD_SETOR"].map(setor_dens)
        gdf["DENS_ATIV_ECON_KM2"] = cod_map.astype("float32")
        pct = gdf["DENS_ATIV_ECON_KM2"].notna().mean() * 100
        print(f"  Cobertura DENS_ATIV_ECON_KM2: {pct:.1f}%  "
              f"(mediana {gdf['DENS_ATIV_ECON_KM2'].median():.0f} estab/km²)")

    # 9b — Validação de estabelecimentos (COD_ESPECIE 6 e 7)
    if "COD_ESPECIE" in gdf.columns:
        estab_mask = gdf["COD_ESPECIE"].isin([6, 7])
        gdf_estab  = gdf.loc[estab_mask, ["geometry"]].copy()
        print(f"  Validando {estab_mask.sum():,} estabelecimentos CNEFE vs CNPJ BHMap ...")

        near = gpd.sjoin_nearest(
            gdf_estab, atv[["geometry"]],
            how="left", max_distance=50.0, distance_col="_dist_atv",
        )
        near = near[~near.index.duplicated(keep="first")]

        gdf["FLAG_ESTAB_VALIDADO"] = np.int8(0)
        gdf["DIST_ATIV_MIN_M"]     = np.nan

        validated = near["_dist_atv"].notna()
        gdf.loc[near[validated].index, "FLAG_ESTAB_VALIDADO"] = np.int8(1)
        gdf.loc[near.index, "DIST_ATIV_MIN_M"] = near["_dist_atv"].values

        n_val = int(gdf["FLAG_ESTAB_VALIDADO"].sum())
        pct_v = n_val / estab_mask.sum() * 100 if estab_mask.sum() > 0 else 0
        print(f"  Estabelecimentos com CNPJ <=50m: {n_val:,} ({pct_v:.1f}%)")

    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 10. SETOR_CENSITARIO (população e densidade)
# ─────────────────────────────────────────────────────────────────────────────
def join_setor_pop(gdf):
    print("[10/12] SETOR_CENSITARIO (população) ...")
    sec_path = PROC / "setor_censitario.parquet"
    if not sec_path.exists():
        print("  AVISO: setor_censitario.parquet não encontrado")
        return gdf

    sec = gpd.read_parquet(sec_path).to_crs(CRS)
    want = ["POP_SETOR", "DOM_SETOR", "DENS_DOM_KM2", "DENS_POP_KM2", "geometry"]
    keep_cols = [c for c in want if c in sec.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], sec[keep_cols], predicate="within")

    for col in [c for c in keep_cols if c != "geometry"]:
        if col in joined.columns:
            gdf[col] = joined[col]

    pct = gdf["DOM_SETOR"].notna().mean() * 100 if "DOM_SETOR" in gdf.columns else 0
    print(f"  Cobertura DOM_SETOR: {pct:.1f}%")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 11. VILA_FAVELA (enriquecida: tipo + plano urbanístico)
# ─────────────────────────────────────────────────────────────────────────────
def join_vila_favela_enriched(gdf):
    print("[11/12] VILA_FAVELA (enriquecida) ...")
    vf_path = PROC / "vila_favela.parquet"
    if not vf_path.exists():
        # Fallback ao shapefile original
        print("  Usando shapefile original como fallback ...")
        vf = gpd.read_file(config.VILAS_FAVELAS_SHP).to_crs(CRS)
        joined = _sjoin_dedup(gdf[["geometry"]], vf[["geometry"]], predicate="within")
        gdf["em_favela"] = joined.index.isin(joined.dropna(how="all").index).astype("int8")
        return gdf

    vf = gpd.read_parquet(vf_path).to_crs(CRS)
    want = ["TIPO_ASSENTAMENTO", "TEM_PLANO_URBANO", "PLANO_URBANO_ORD",
            "QTD_DOMICILIOS", "geometry"]
    keep_cols = [c for c in want if c in vf.columns]
    joined = _sjoin_dedup(gdf[["geometry"]], vf[keep_cols], predicate="within")

    gdf["em_favela"] = joined["TIPO_ASSENTAMENTO"].notna().astype("int8")
    for col in [c for c in keep_cols if c not in ("geometry",)]:
        if col in joined.columns:
            gdf[col] = joined[col]

    n = int(gdf["em_favela"].sum())
    pct = gdf["em_favela"].mean() * 100
    print(f"  em_favela: {n:,} ({pct:.1f}%)")
    if "TIPO_ASSENTAMENTO" in gdf.columns:
        print(f"    {dict(gdf['TIPO_ASSENTAMENTO'].value_counts().head(3))}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 12. Flags internas (sem join espacial)
# ─────────────────────────────────────────────────────────────────────────────
def add_internal_flags(gdf):
    print("[12/12] Flags internas (sem join) ...")

    # Qualidade do dado de referência BHMap
    if "SITUACAO_P" in gdf.columns:
        gdf["FLAG_NUMERO_INVALIDO"] = (
            gdf["SITUACAO_P"].str.contains("Inválido", na=False)
        ).astype("int8")
        n_inv = int(gdf["FLAG_NUMERO_INVALIDO"].sum())
        print(f"  FLAG_NUMERO_INVALIDO: {n_inv:,} ({n_inv/len(gdf)*100:.1f}%)")

    # Endereço com complemento preenchido (apto, sala, etc.)
    if "COMPLEMENTO" in gdf.columns:
        gdf["FLAG_COMPLEMENTO"] = (
            gdf["COMPLEMENTO"].notna() &
            (gdf["COMPLEMENTO"].astype(str).str.strip() != "") &
            (gdf["COMPLEMENTO"].astype(str).str.strip().str.upper() != "NAN")
        ).astype("int8")
        n_comp = int(gdf["FLAG_COMPLEMENTO"].sum())
        print(f"  FLAG_COMPLEMENTO: {n_comp:,} ({n_comp/len(gdf)*100:.1f}%)")

    # Estabelecimento não-residencial
    if "COD_ESPECIE" in gdf.columns:
        gdf["FLAG_ESTABELECIMENTO"] = gdf["COD_ESPECIE"].isin([6, 7]).astype("int8")

    # Tipo de via do BHMap (já está em SIGLA_TIPO desde v2)
    # Sem duplicação — apenas garantir que o campo existe com nome claro
    if "SIGLA_TIPO" in gdf.columns and "VIA_SIGLA_BH" not in gdf.columns:
        gdf["VIA_SIGLA_BH"] = gdf["SIGLA_TIPO"]

    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# Variáveis derivadas e normalizações
# ─────────────────────────────────────────────────────────────────────────────
def add_derived(gdf):
    print("[DER] Variáveis derivadas ...")

    # ── Normalizações lineares ────────────────────────────────────────────────
    if "PADRAO_SCORE" in gdf.columns:
        mask_const = gdf.get("FLAG_TERRITORIAL", pd.Series(0, index=gdf.index)) == 0
        gdf["PADRAO_NORM"] = np.nan
        gdf.loc[mask_const, "PADRAO_NORM"] = (
            (gdf.loc[mask_const, "PADRAO_SCORE"] - 1) / 4
        ).astype("float32")

    if "INFRA_SCORE" in gdf.columns:
        gdf["INFRA_NORM"] = (gdf["INFRA_SCORE"] / 8.0).astype("float32")

    if "IVS_SCORE" in gdf.columns:
        gdf["IVS_NORM"] = ((gdf["IVS_SCORE"] - 1) / 3.0).astype("float32")

    if "PAV_EST" in gdf.columns:
        gdf["PAV_LOG"] = np.log1p(gdf["PAV_EST"].fillna(1)).astype("float32")

    # ── Compostos ────────────────────────────────────────────────────────────
    ivs_vulner = gdf.get("IVS_SCORE", pd.Series(0.0, index=gdf.index)).fillna(0) >= 3
    em_risco   = gdf.get("em_risco", pd.Series(0, index=gdf.index)).astype(bool)
    gdf["VULNERAB_COMPOSTA"] = (ivs_vulner & em_risco).astype("int8")

    nao_territ = gdf.get("FLAG_TERRITORIAL", pd.Series(0, index=gdf.index)) == 0
    infra_ok   = gdf.get("INFRA_SCORE", pd.Series(np.nan, index=gdf.index)).fillna(0) >= 4
    gdf["CONTEXTO_FORMAL"] = (nao_territ & infra_ok).astype("int8")

    if "IVS_SCORE" in gdf.columns:
        gdf["IVS_ALTO"] = (gdf["IVS_SCORE"] >= 3).astype("int8")

    # ── PAV_TIPO categórico ───────────────────────────────────────────────────
    if "PAV_EST" in gdf.columns:
        pav = gdf["PAV_EST"].fillna(1)
        gdf["PAV_TIPO"] = pd.cut(
            pav, bins=[0, 1, 2, 5, 10, 9999],
            labels=["1_pav", "2_pav", "3-5_pav", "6-10_pav", "10+_pav"], right=True,
        ).astype(str)
        gdf.loc[gdf["PAV_EST"].isna(), "PAV_TIPO"] = np.nan

    # ── Idade do imóvel ───────────────────────────────────────────────────────
    if "ANO_MIN_CONSTRUCAO" in gdf.columns:
        ano = pd.to_numeric(gdf["ANO_MIN_CONSTRUCAO"], errors="coerce")
        gdf["IDADE_IMOVEL"] = (2022 - ano).clip(lower=0).astype("float32")

    # ── Taxa de ocupação do lote ─────────────────────────────────────────────
    if "AREA_CONSTR_TOTAL" in gdf.columns and "AREA_TERRENO" in gdf.columns:
        area_t = pd.to_numeric(gdf["AREA_TERRENO"], errors="coerce")
        area_c = pd.to_numeric(gdf["AREA_CONSTR_TOTAL"], errors="coerce")
        gdf["TAXA_OCUPACAO"] = (area_c / area_t.replace(0, np.nan)).clip(0, 5).astype("float32")

    # ── Classe de altitude ───────────────────────────────────────────────────
    if "ALTITUDE_MDT" in gdf.columns:
        gdf["ALTITUDE_CLASSE"] = pd.cut(
            gdf["ALTITUDE_MDT"],
            bins=ALTITUDE_BINS, labels=ALTITUDE_LABELS, right=False,
        ).astype(str)
        gdf.loc[gdf["ALTITUDE_MDT"].isna(), "ALTITUDE_CLASSE"] = np.nan

    print(f"  VULNERAB_COMPOSTA=1: {int(gdf['VULNERAB_COMPOSTA'].sum()):,}")
    print(f"  CONTEXTO_FORMAL=1:   {int(gdf['CONTEXTO_FORMAL'].sum()):,}")
    if "FLAG_NUMERO_INVALIDO" in gdf.columns:
        print(f"  FLAG_NUMERO_INVALIDO=1: {int(gdf['FLAG_NUMERO_INVALIDO'].sum()):,}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# Sumário de cobertura
# ─────────────────────────────────────────────────────────────────────────────
def print_coverage_summary(gdf):
    print("\n=== SUMÁRIO DE COBERTURA — master expandido ===")
    groups = {
        "Vulnerabilidade": ["IVS_SCORE", "IVS_NORM", "IVS_ALTO"],
        "Risco":           ["em_risco", "em_inundacao", "em_escorregamento"],
        "Tipologia":       ["TIPOLOGIA_BROAD", "TIPOLOGIA_CLASSE", "MORFOLOGIA"],
        "Cadastro":        ["INFRA_SCORE", "PADRAO_SCORE", "ANO_MIN_CONSTRUCAO",
                           "IND_GALERIA_PLUVIAL", "IND_PAVIMENTACAO", "IND_REDE_ESGOTO",
                           "AREA_TERRENO", "AREA_CONSTR_TOTAL", "TAXA_OCUPACAO"],
        "Edificação":      ["PAV_EST", "PAV_TIPO", "ALTITUDE_MDT", "RUGOSIDADE_MDT",
                           "AREA_EDIFICACAO", "ALTITUDE_CLASSE", "IDADE_IMOVEL"],
        "Viária":          ["VIA_CLASSIFICA", "VIA_HIERARQUIA", "VIA_TIPO_LOG",
                           "VIA_LARGURA_ORD", "FLAG_BECO"],
        "Declividade":     ["DECLIV_MEDIANA", "DECLIV_DESVPAD", "DECLIV_CLASSE"],
        "Zoneamento":      ["ZONA_TIPO", "ZONA_CLASSE", "FLAG_ZONA_SOCIAL"],
        "Atividade Econ":  ["DENS_ATIV_ECON_KM2", "FLAG_ESTAB_VALIDADO", "DIST_ATIV_MIN_M"],
        "Setor Censit":    ["POP_SETOR", "DOM_SETOR", "DENS_DOM_KM2"],
        "Informalidade":   ["em_favela", "TIPO_ASSENTAMENTO", "TEM_PLANO_URBANO",
                           "PLANO_URBANO_ORD", "VULNERAB_COMPOSTA"],
        "Flags internas":  ["FLAG_NUMERO_INVALIDO", "FLAG_COMPLEMENTO", "FLAG_ESTABELECIMENTO"],
    }
    print(f"  {'Grupo':<18} {'Coluna':<30} {'Não-nulo':>10}  {'Cobertura':>10}")
    print("  " + "-" * 75)
    for grp, cols in groups.items():
        for col in cols:
            if col in gdf.columns:
                nn  = gdf[col].notna().sum()
                pct = nn / len(gdf) * 100
                print(f"  {grp:<18} {col:<30} {nn:>10,}  {pct:>9.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    console.rule("[bold]ETL — Enriquecimento Master Parquet")

    gdf = load_base()
    gdf = join_ivs(gdf)
    gdf = join_area_risco(gdf)
    gdf = join_lote_ctm(gdf)
    gdf = join_cadastro(gdf)
    gdf = join_edificacao(gdf)
    gdf = join_via_classifica(gdf)
    gdf = join_declividade(gdf)
    gdf = join_zoneamento(gdf)
    gdf = join_atividade_economica(gdf)
    gdf = join_setor_pop(gdf)
    gdf = join_vila_favela_enriched(gdf)
    gdf = add_internal_flags(gdf)
    gdf = add_derived(gdf)

    print_coverage_summary(gdf)

    out = OUT / "cnefe_master_metrics.parquet"
    print(f"\n[SAVE] Salvando {out.name} ({len(gdf):,} registros, {len(gdf.columns)} colunas) ...")
    gdf.to_parquet(out)
    print(f"  -> {out.stat().st_size/1e6:.1f} MB")
    print("\n[DONE] cnefe_master_metrics.parquet gerado com sucesso.")
    print(f"       Total de colunas contextuais: {len(gdf.columns) - 30} (sobre base de 30)")
