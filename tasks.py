"""
Orquestrador de tarefas do projeto via PyInvoke.

Uso:
    inv setup    — Instala dependências e verifica dados brutos.
    inv clean    — Limpa outputs e dados processados.
    inv etl      — Executa o pipeline ETL (DuckDB + Pandas).
    inv match    — Executa notebooks de ingestão e matching.
    inv analyze  — Executa notebooks analíticos (03–06).
    inv all      — Pipeline completo end-to-end.
"""

import sys

from invoke import task
from src.config import (
    CNEFE_RAW_FILE,
    BHMAP_RAW_FILE,
    PROCESSED_DATA_DIR,
    FIGURES_DIR,
    MAPS_DIR,
    TABLES_DIR,
)

# Timeout padrão para execução de notebooks (em segundos)
NBCONVERT_TIMEOUT = 600


def _nbconvert_cmd(notebook: str) -> str:
    """Gera o comando nbconvert com timeout padronizado."""
    return (
        f"jupyter nbconvert --to notebook --execute {notebook} "
        f"--inplace --ExecutePreprocessor.timeout={NBCONVERT_TIMEOUT}"
    )


@task
def setup(c):
    """Instala dependências e verifica a integridade dos arquivos brutos (CNEFE e BHMap)."""
    print("[SETUP] 1/2: Instalando/Atualizando bibliotecas do requirements.txt...")
    c.run("pip install -r requirements.txt", hide=False)

    print("\n[SETUP] 2/2: Verificando integridade dos dados brutos...")

    if not CNEFE_RAW_FILE.exists():
        print(f"\n[ERRO CRÍTICO] Arquivo CNEFE não encontrado em: {CNEFE_RAW_FILE}")
        print("-> AVALIADOR/USUÁRIO: Baixe o dataset CNEFE 2022 (Minas Gerais) do portal do IBGE.")
        print("-> Salve o arquivo JSON (aprox 5.5GB) no caminho exato acima antes de prosseguir.\n")
        sys.exit(1)

    if not BHMAP_RAW_FILE.exists():
        print(f"\n[ERRO CRÍTICO] Arquivo BHMap Shapefile não encontrado em: {BHMAP_RAW_FILE}")
        print("-> AVALIADOR/USUÁRIO: Baixe o dataset de Endereços da PBH (BHMap).")
        print("-> Salve os arquivos do shapefile (.shp e adjacentes) no caminho exato acima.\n")
        sys.exit(1)

    print("[SETUP] Todos os arquivos brutos estão presentes! O projeto está pronto para rodar o ETL.")


@task
def clean(c):
    """Limpa completamente os diretórios de outputs e dados processados."""
    import glob
    print("[CLEAN] Limpando pastas: data/processed e outputs/* ...")

    dirs_to_clean = [
        str(PROCESSED_DATA_DIR / "*"),
        str(FIGURES_DIR / "*"),
        str(MAPS_DIR / "*"),
        str(TABLES_DIR / "*"),
    ]

    for str_pattern in dirs_to_clean:
        for f in glob.glob(str_pattern):
            from pathlib import Path
            p = Path(f)
            if p.is_file():
                try:
                    p.unlink()
                except Exception as e:
                    print(f"Erro ao remover {f}: {e}")

    print("[CLEAN] Sucesso! Repositório resetado.")


@task
def etl(c):
    """Executa a extração, filtro e normalização vetorial pesada via DuckDB (Passo 0)."""
    print("[ETL] Rodando Pipeline DuckDB (qg_810_endereco_UF31 -> Parquet)...")
    c.run("python -m src.etl_pipeline")


@task
def match(c):
    """Executa a reprojeção geográfica (01) e o Motor Híbrido de Pareamento (02)."""
    print("[MATCH] Executando Notebook 01: Setup & Ingest (Reprojeção Geográfica)...")
    c.run(_nbconvert_cmd("notebooks/01_setup_ingest.ipynb"))

    print("[MATCH] Executando Notebook 02: Motor Híbrido de Pareamento (Espacial + Fuzzy)...")
    c.run(_nbconvert_cmd("notebooks/02_address_matching.ipynb"))


@task
def analyze(c):
    """Executa os notebooks analíticos (03–06) para regerar mapas e gráficos."""
    notebooks = [
        ("03", "Análise de Completude", "notebooks/03_completeness_analysis.ipynb"),
        ("04", "Qualidade e Acurácia (RMSE)", "notebooks/04_quality_and_accuracy.ipynb"),
        ("05", "Visualização de Incerteza Espacial (KDE)", "notebooks/05_spatial_uncertainty_viz.ipynb"),
        ("06", "Incerteza Socio-Espacial e Ambiental (OLS)", "notebooks/06_socio_spatial_vulnerability.ipynb"),
    ]
    for num, desc, path in notebooks:
        print(f"[ANALYZE] Executando Notebook {num}: {desc}...")
        c.run(_nbconvert_cmd(path))


@task
def all(c):
    """Pipeline nuclear: Roda absolutamente tudo (Setup -> Clean -> ETL -> Match -> Analyze)."""
    print("[ALL] Iniciando Pipeline Completo (End-to-End)...")
    setup(c)
    clean(c)
    etl(c)
    match(c)
    analyze(c)
    print("[ALL] Pipeline finalizado com sucesso! Verifique a pasta 'outputs/'.")
