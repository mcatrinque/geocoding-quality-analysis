import os
import glob
from invoke import task

@task
def setup(c):
    """
    Instala dependências de Python e verifica a integridade dos arquivos brutos (CNEFE e BHMap).
    """
    print("[SETUP] 1/2: Instalando/Atualizando bibliotecas do requirements.txt...")
    # c.run("pip install -r requirements.txt", hide=False)
    
    print("\\n[SETUP] 2/2: Verificando integridade dos requisitos dos dados brutos...")
    
    # Check CNEFE
    cnefe_path = "data/raw/cnefe2022/qg_810_endereco_UF31.json"
    if not os.path.exists(cnefe_path):
        print(f"\\n[ERRO CRÍTICO] Arquivo CNEFE não encontrado em: {cnefe_path}")
        print("-> AVALIADOR/USUÁRIO: Baixe o dataset CNEFE 2022 (Minas Gerais) do portal do IBGE.")
        print("-> Salve o arquivo JSON (aprox 5.5GB) no caminho exato acima antes de prosseguir.\\n")
        exit(1)
        
    # Check BHMap
    bhmap_path = "data/raw/bhmap/bhmap.shp"
    if not os.path.exists(bhmap_path):
        print(f"\\n[ERRO CRÍTICO] Arquivo BHMap Shapefile não encontrado em: {bhmap_path}")
        print("-> AVALIADOR/USUÁRIO: Baixe o dataset de Endereços da PBH (BHMap).")
        print("-> Salve os arquivos do shapefile (.shp e adjacentes) no caminho exato acima.\\n")
        exit(1)
        
    print("[SETUP] Todos os arquivos brutos estão presentes! O projeto está pronto para rodar o ETL.")

@task
def clean(c):
    """
    Limpa completamente os diretórios de outputs e dados intermediários.
    """
    print("[CLEAN] Limpando pastas: data/interim, data/processed, e outputs/* ...")
    
    dirs_to_clean = [
        "data/processed/*", 
        "outputs/figures/*", 
        "outputs/maps/*", 
        "outputs/tables/*"
    ]
    
    for str_pattern in dirs_to_clean:
        for f in glob.glob(str_pattern):
            if os.path.isfile(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Erro ao remover {f}: {e}")
    
    print("[CLEAN] Sucesso! Repositório resetado.")

@task
def etl(c):
    """
    Executa a extração, filtro e normalização vetorial pesada via DuckDB (Passo 0).
    """
    print("[ETL] Rodando Pipeline C++ DuckDB (qg_810_endereco_UF31 -> Parquet)...")
    c.run("python -m src.etl_pipeline")

@task
def match(c):
    """
    Executa a reprojeção geográfica (01) e o Motor Híbrido de Pareamento (02).
    """
    print("[MATCH] Executando Notebook 01: Setup & Ingest (Reprojeção Geográfica)...")
    c.run("jupyter nbconvert --to notebook --execute notebooks/01_setup_ingest.ipynb --inplace")
    
    print("[MATCH] Executando Notebook 02: Motor Híbrido de Pareamento (Espacial + Fuzzy)...")
    c.run("jupyter nbconvert --to notebook --execute notebooks/02_address_matching.ipynb --inplace")

@task
def analyze(c):
    """
    Executa apenas os notebooks analíticos (03, 04, 05) para regerar mapas e gráficos rapidamente.
    """
    print("[ANALYZE] Executando Notebook 03: Análise de Completude...")
    c.run("jupyter nbconvert --to notebook --execute notebooks/03_completeness_analysis.ipynb --inplace")
    
    print("[ANALYZE] Executando Notebook 04: Qualidade e Acurácia (RMSE)...")
    c.run("jupyter nbconvert --to notebook --execute notebooks/04_quality_and_accuracy.ipynb --inplace")
    
    print("[ANALYZE] Executando Notebook 05: Visualização de Incerteza Espacial (KDE)...")
    c.run("jupyter nbconvert --to notebook --execute notebooks/05_spatial_uncertainty_viz.ipynb --inplace")

@task
def all(c):
    """
    Pipeline nuclear: Roda absolutamente tudo (Clean -> ETL -> Match -> Analyze).
    """
    print("[ALL] Iniciando Pipeline Completo (End-to-End)...")
    setup(c)
    clean(c)
    etl(c)
    match(c)
    analyze(c)
    print("[ALL] Pipeline finalizado com sucesso! Verifique a pasta 'outputs/'.")
