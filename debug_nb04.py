
import pandas as pd
from src.metrics import infer_bhmap_typology, categorize_cnefe_species
from src import config

try:
    # 1. Carregar dados
    print("Loading data...")
    df_bhmap = pd.read_parquet(config.BHMAP_PROCESSED_FILE)
    df_matched = pd.read_parquet(config.PROCESSED_DATA_DIR / 'cnefe_match_bhmap.parquet')

    # 2. Aplicar categorização
    print("Applying categorization...")
    df_matched = categorize_cnefe_species(df_matched)
    print(f"Columns in df_matched after categorization: {df_matched.columns.tolist()}")
    if 'categoria_analitica' in df_matched.columns:
        print("Success: 'categoria_analitica' found in df_matched")
    else:
        print("Error: 'categoria_analitica' NOT found in df_matched")

    # 3. Inferir tipologia
    print("Inferring BHMap typology...")
    df_bhmap_typ = infer_bhmap_typology(df_bhmap)

    # 4. Cruzar
    print("Merging...")
    df_check = df_matched.merge(
        df_bhmap_typ[['id_bhmap', 'tipologia_bhmap', 'address_count']], 
        on='id_bhmap', 
        how='inner'
    )
    print(f"Columns in df_check: {df_check.columns.tolist()}")

    # 5. Crosstab
    print("Running crosstab...")
    cross_tab = pd.crosstab(
        df_check['categoria_analitica'], 
        df_check['tipologia_bhmap'], 
        normalize='index'
    )
    print("Success: Crosstab completed")
    print(cross_tab)

except Exception as e:
    print(f"Caught exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
