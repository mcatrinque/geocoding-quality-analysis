
import nbformat as nbf
from pathlib import Path

def clean_and_patch_nb(nb_path, section_header, new_cells_func):
    nb = nbf.read(nb_path, as_version=4)
    
    # Remover células de expansões anteriores
    # Procuramos pelo cabeçalho da seção
    cleaned_cells = []
    skip = False
    for cell in nb.cells:
        if cell.cell_type == 'markdown' and section_header in cell.source:
            skip = True # Começa a pular a seção antiga
            continue
        
        # Se encontrarmos o próximo cabeçalho de seção (## Conclusões) paramos de pular
        if skip and cell.cell_type == 'markdown' and "## Conclus" in cell.source:
            skip = False
            
        if not skip:
            cleaned_cells.append(cell)
            
    nb.cells = cleaned_cells
    
    # Inserir as novas células antes da conclusão
    insert_idx = len(nb.cells) - 1
    new_cells = new_cells_func()
    
    for i, cell in enumerate(new_cells):
        nb.cells.insert(insert_idx + i, cell)
        
    nbf.write(nb, nb_path)
    print(f"{nb_path} cleaned and patched.")

def get_nb03_cells():
    return [
        nbf.v4.new_markdown_cell("### §4 Analise de Pareamento por Categoria\n\nAqui avaliamos a **taxa de sucesso** de integração para cada segmento do CNEFE. Isso nos permite identificar se certas tipologias de endereços são 'invisíveis' ou submetidas a maiores dificuldades de matching na base do BHMap."),
        nbf.v4.new_code_cell("""
from src.metrics import calculate_match_rate_by_category, categorize_cnefe_species
from src import config

# Carregar dados originais e pareados
df_cnefe_raw = pd.read_parquet(config.CNEFE_PROCESSED_FILE)
df_matched = pd.read_parquet(config.PROCESSED_DATA_DIR / 'cnefe_match_bhmap.parquet')

# Aplicar categorização base
df_cnefe_raw = categorize_cnefe_species(df_cnefe_raw)

# Calcular taxa de match
match_rate_df = calculate_match_rate_by_category(df_cnefe_raw, df_matched['id_cnefe'].unique())
match_rate_df = match_rate_df.sort_values('Match Rate (%)', ascending=False)

# Exibir e salvar
display(match_rate_df)
match_rate_df.to_csv(config.TABLES_DIR / '03_match_rate_by_category.csv', index=False)
"""),
        nbf.v4.new_markdown_cell("> **Interpretação Analítica**: Uma taxa de pareamento significativamente menor em categorias como 'Comercial' ou 'Serviço Público' sugere que a base de endereços oficial da prefeitura (BHMap) pode ter um viés residencial, ou que a nomenclatura de estabelecimentos no CNEFE diverge drasticamente da padronização de logradouros municipal.")
    ]

def get_nb04_cells():
    return [
        nbf.v4.new_markdown_cell("### §4 Consistência Semântica Espacial (Cross-Base)\n\nNesta análise, validamos a categoria do CNEFE contra o comportamento observado no BHMap. Como o BHMap nǜo possui um campo de 'uso', inferimos a **Tipologia Vertical** para coordenadas que concentram múltiplos endereços. Cruzamos esses 'fatos espaciais' para medir a harmonia entre as bases."),
        nbf.v4.new_code_cell("""
from src.metrics import infer_bhmap_typology, categorize_cnefe_species
import plotly.express as px
from src import config

# Carregar BHMap e pareados
df_bhmap = pd.read_parquet(config.BHMAP_PROCESSED_FILE)
df_matched = pd.read_parquet(config.PROCESSED_DATA_DIR / 'cnefe_match_bhmap.parquet')

# Aplicar categorização (Essencial para cross-tab)
df_matched = categorize_cnefe_species(df_matched)

# Inferir tipologia no Gold Standard (BHMap) baseada em densidade
df_bhmap_typ = infer_bhmap_typology(df_bhmap)

# Cruzar com o dataset de validação
df_check = df_matched.merge(
    df_bhmap_typ[['id_bhmap', 'tipologia_bhmap', 'address_count']], 
    on='id_bhmap', 
    how='inner'
)

# Criar matriz de consistência: CNEFE Categoria vs BHMap Inferred Typology
cross_tab = pd.crosstab(
    df_check['categoria_analitica'], 
    df_check['tipologia_bhmap'], 
    normalize='index'
) * 100

# Visualizar Consistência
fig = px.imshow(
    cross_tab,
    labels=dict(x="BHMap (Inferred)", y="CNEFE (Stated)", color="%"),
    x=['Horizontal', 'Vertical'],
    y=cross_tab.index,
    text_auto=".1f",
    title="Matriz de Consistência Semântica: CNEFE vs BHMap",
    color_continuous_scale='Blues'
)
fig.show()

# Salvar insights
cross_tab.to_csv(config.TABLES_DIR / '04_semantic_consistency_matrix.csv')
fig.write_image(str(config.FIGURES_DIR / "04_semantic_consistency_heatmap.png"))
"""),
        nbf.v4.new_markdown_cell("**Interpretação Analítica**: Esperamos que a categoria 'Residencial Vertical' do CNEFE apresente alta concentração na coluna 'Vertical' do BHMap. Desvios (ex: CNEFE Vertical em BHMap Horizontal) indicam ou erro de classificação no censo ou que a base municipal consolida múltiplos apartamentos em um único registro simplificado.")
    ]

if __name__ == "__main__":
    clean_and_patch_nb(
        Path("notebooks/03_completeness_analysis.ipynb"), 
        "### §4 Analise de Pareamento por Categoria", 
        get_nb03_cells
    )
    clean_and_patch_nb(
        Path("notebooks/04_quality_and_accuracy.ipynb"), 
        "### §4 Consistência Semântica Espacial (Cross-Base)", 
        get_nb04_cells
    )
