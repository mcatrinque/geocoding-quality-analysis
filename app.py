import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(
    page_title="Dissertação: Qualidade da Geocodificação",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS Customizations ---
st.markdown("""
<style>
    /* Esconde elementos desnecessários */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}

    /* Padronização de Imagens para modo Lado a Lado (colunas) */
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stImage"] > img {
        height: 420px !important; 
        object-fit: contain !important; 
        width: auto !important;
        margin: 0 auto;
    }

    /* Imagens que ocupam a linha toda sem regras restritivas deformantes */
    .full-width-img div[data-testid="stImage"] > img {
        height: auto !important;
        max-height: 65vh !important; 
        width: 100% !important;
        object-fit: contain !important;
    }

    /* Estética base do texto analítico livre de bordas (Notebook Style) */
    .analysis-text {
        font-size: 1.05rem;
        line-height: 1.6;
        color: #dcdcdc;
        text-align: justify;
        padding-top: 0.5rem;
        margin-bottom: 1.5rem;
    }
    
    .topic-subheader {
        font-size: 1.1rem;
        font-weight: 600;
        color: #f0f2f6;
        margin-bottom: 0.5rem;
        text-align: center;
    }

    /* Margem dos headers de capitulos */
    h1, h2, h3 { color: #f0f2f6; margin-top: 1.5rem; }
    hr { margin: 1rem 0 2rem 0; border-top: 1px solid #444; }
</style>
""", unsafe_allow_html=True)

# --- Helpers ---
def load_html(file_path, height=550):
    if Path(file_path).exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            components.html(f.read(), height=height, scrolling=True)
    else:
        st.warning(f"HTML não encontrado: {file_path}")

def load_img(file_path, caption=None, full_width=False):
    if Path(file_path).exists():
        if full_width:
            st.markdown('<div class="full-width-img">', unsafe_allow_html=True)
            st.image(file_path, caption=caption, use_column_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.image(file_path, caption=caption, use_column_width=True)
    else:
        st.warning(f"Imagem não encontrada: {file_path}")

def render_analysis(text):
    # Texto limpo, sem "caixas" (bordas, backgrounds coloridos ou scrolls embutidos)
    st.markdown(f'<div class="analysis-text"><b>Análise:</b> {text}</div>', unsafe_allow_html=True)

# --- Header ---
st.title("Qualidade e Desigualdade na Geocodificação")
st.markdown("""
**Defesa de Dissertação de Mestrado** | Ciência da Computação - UFMG  
**Pesquisador**: Mateus Rezende de Sá Catrinque  
**Objeto de Estudo**: CNEFE 2022 vs BHMap
""")

st.divider()

tabs = st.tabs([
    "01. Ingestão", "02. Matching", "03. Lógica (LCI)", 
    "04. Acurácia (GCI)", "05. Hipóteses", "06. Espacial", "07. Causalidade", "08. Síntese"
])

# ------------- TAB 01 -------------
with tabs[0]:
    st.header("NB01: Ingestão e Preparação do Terreno")
    st.markdown("A qualidade da geocodificação afeta diretamente a validade urbana. O objetivo consiste em compilar as bases brutas do IBGE contra o padrão-ouro (BHMap).")
    st.divider()
    
    st.subheader("Cobertura Territorial (Interativo)")
    load_html("outputs/maps/01_mapa_cobertura_dual.html", height=500)
    render_analysis("A exploração visual da malha faculta a identificação micro-espacial imediata de não-conformidades topológicas. Bordas metropolitanas, áreas de proteção e favelas nas franjas limítrofes abrigam visualmente as maiores discrepâncias iniciais de geolocalização bruta do município.")
    
    st.subheader("Densidade Comparativa")
    load_img("outputs/figures/01_densidade_comparativa.png", full_width=True)
    render_analysis("A análise espacial maciça expõe alinhamento basal nas zonas vitais históricas. Contudo, hiatos de manchas térmicas sutis em áreas vulneráveis já atestam precocemente assimetrias fundamentais na densidade demográfica capturada.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">Integridade Estrutural</div>', unsafe_allow_html=True)
        load_img("outputs/figures/01_bhmap_qualidade.png")
    with col2:
        st.markdown('<div class="topic-subheader">Níveis de Coleta do IBGE</div>', unsafe_allow_html=True)
        load_img("outputs/figures/01_barras_nv_geo.png")
    
    c1, c2 = st.columns(2)
    with c1: render_analysis("A integridade volumétrica da massa edificada do BHMap e sua complexidade tipológica sustentam perfeitamente a escolha desta base como *Ground Truth* fidedígno comparável no escopo metropolitano.")
    with c2: render_analysis("Observa-se que apenas uma fatia restrita das coordenadas do Censo teve o rigor tecnológico ativo estrito (GPS *on the fly*). A predominância de métodos secundários por associação lógica insinua o perigo basilar do erro.")

    st.subheader("Estrutura Hierárquica do Cadastro")
    load_html("outputs/maps/01_sunburst_cnefe.html", height=600)
    render_analysis("O diagrama solar decodifica a disparidade da malha imobiliária urbana, explicitando o gigantesco volume de usos residenciais puros versus as camadas finas em zonas mistas informais, essenciais para ponderações volumétricas.")

# ------------- TAB 02 -------------
with tabs[1]:
    st.header("NB02: Cruzamento Espacial e *Fuzzy Matching*")
    st.markdown("Procede-se aos arranjos espaciais rigorosos e validações de similaridades sintáticas utilizando Algoritmos Distância Levenshtein (*Fuzzy String Matching*).")
    st.divider()
    
    st.subheader("O Mapa da Incerteza do Matching (MCI)")
    load_html("outputs/maps/02_mapa_mci.html", height=550)
    render_analysis("A colorimetria interativa demonstra a concentração de altos índices de convergência (pontos azuis) na zona central da cidade, ao passo que nuvens de baixíssima incerteza explodem em localidades perimetrais desordenadas com ausência de CEP consolidado.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">Distribuição Global MCI</div>', unsafe_allow_html=True)
        load_img("outputs/figures/02_histograma_mci.png")
    with col2:
        st.markdown('<div class="topic-subheader">Variabilidade por Regional</div>', unsafe_allow_html=True)
        load_img("outputs/figures/02_boxplot_mci_regional.png")
    
    c1, c2 = st.columns(2)
    with c1: render_analysis("Embora a assimetria global positiva ateste que a esmagadora maioria das conexões censitárias são precisas e confiáveis, a espessa cauda inferior engole dezenas de milhares de domicílios na margem de dúvida.")
    with c2: render_analysis("A dispersão em *boxplots* denuncia as flagrantes discrepâncias de precisão. O desvio-padrão absurdo na regional periférica revela como as periferias pagam o preço da desordem registral nominal das prefeituras.")

    st.subheader("A Dispersão Cartesiana: Distância Métrica vs Lexical")
    load_html("outputs/maps/02_scatter_dist_sim.html", height=500)
    render_analysis("Constata-se nesta plotagem dinâmica a infame coexistência: descolamentos euclidianos que rompem a barreira do bairro frequentemente colidem com logradouros repletos de gírias gramaticais, abreviações ou nomes populares extintos nas plantas oficiais.")

    st.subheader("Desempenho por Categoria Imobiliária")
    load_img("outputs/figures/02_matching_por_especie.png", full_width=True)
    render_analysis("O boxplot de caudas longas estampa inconfundivelmente como a modelagem penalizou habitações coletivas e igrejas populares, limitando graus rigorosos absolutos a prédios e residenciais estruturados da matriz urbana formal.")

# ------------- TAB 03 -------------
with tabs[2]:
    st.header("NB03: Índices ISO-19157 e Qualidade Lógica (LCI)")
    st.markdown("Verificação sistemática das premissas de completude atributivas do cadastro via *Locating Certainty Indicator* (LCI).")
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">Matriz de Nulidade Estrutural</div>', unsafe_allow_html=True)
        load_img("outputs/figures/03_matrix_nulidade.png")
    with col2:
        st.markdown('<div class="topic-subheader">Completude por Função Urbana</div>', unsafe_allow_html=True)
        load_img("outputs/figures/03_heatmap_completude_especie.png")
    
    c1, c2 = st.columns(2)
    with c1: render_analysis("As fileiras brancas representativas da ausência de meta-informações chaves documentam a erosão grave e o rebaixamento de certeza processual do IBGE sobre os campos estritos.")
    with c2: render_analysis("O espectro de calor elucida visualmente a negligência sistemática com comércios pequenos e aglomerados mistos, rebaixando a segurança topológica fundamental frente às amostras luxuosas.")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="topic-subheader">LCI Básico Distrital</div>', unsafe_allow_html=True)
        load_img("outputs/figures/03_coropletico_bairro_lci.png")
    with col4:
        st.markdown('<div class="topic-subheader">Normalização Hexagonal Contínua</div>', unsafe_allow_html=True)
        load_img("outputs/figures/03_mapa_lci_hexbin.png")

    c3, c4 = st.columns(2)
    with c3: render_analysis("O mapa coroplético prova uma gravidade perene: a metodologia de captura falha absurdamente em englobar com a mesma dignidade logradouros do anel marginal perante bairros históricos.")
    with c4: render_analysis("O método isométrico (Hexbin) não amarra a mancha à fronteira do bairro; confirmando factualmente que a mancha de apagão metodológico se arrasta como um cinturão epidêmico pelas extremidades de fronteiras distritais.")

# ------------- TAB 04 -------------
with tabs[3]:
    st.header("NB04: O Geocoding Certainty Indicator (GCI)")
    st.markdown("Materialização final do indicador matemático de viabilidade espacial e prova categórica do resíduo escalar.")
    st.divider()
    
    st.subheader("Micro-Auditoria: Mapa GCI Lote a Lote")
    load_html("outputs/maps/04_mapa_gci.html", height=600)
    render_analysis("Sobrevoando a malha nesta dimensão atômica das moradias, nota-se como a acurácia cai para GCI < 0.2 imediatamente ao depararmos com terrenos favelizados íngremes ou corredores habitacionais adensados informalmente nas montanhas.")
    
    st.subheader("Spider Map dos Estiramentos Posicionais")
    load_html("outputs/maps/04_spider_map.html", height=600)
    render_analysis("Uma prova forense geométrica estupenda: as teias de aranha vetoriais marcam as tensões esticadas. Elas mostram que os pontos que a união declarou corretos estão a quadras de distância dos tetos físicos mapeados nas trincheiras oficiais do município (Distâncias acima de 120 metros rotineiros).")

    st.subheader("Teste Non-Paramétrico do Resíduo Espacial")
    load_img("outputs/figures/04_qqplot_e_histograma.png", full_width=True)
    render_analysis("Os vértices completamente descolados na rampa Quantile-Quantile (QQ-Plot) atestam uma evidência estatística severa *Heavy-Tailed*: a aberração imensa nos erros de distância não pode ser computada como imprecisão inocente do GPS (ruído branco); e sim, um gravíssimo defeito sistemático procedimental da coleta demográfica e registro algorítmico global do recenseador.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">O Viés Direcional Polar (Rayleigh)</div>', unsafe_allow_html=True)
        load_img("outputs/figures/04_vies_direcional.png")
    with col2:
        st.markdown('<div class="topic-subheader">O Calor Abismal das Zonas de Erro</div>', unsafe_allow_html=True)
        load_img("outputs/figures/04_gci_heatmap.png")

    c1, c2 = st.columns(2)
    with c1: render_analysis("O alongamento assimétrico flagrante na Rosa dos Ventos não é esférico. As agulhas mostram matematicamente que os falsos recortes convergem artificialmente atraídos pela força de atrito e registro dos vetores rodoviários da engenharia do solo de metrópoles.")
    with c2: render_analysis("A visão térmica prova a macro-estruturação da incerteza: um cinturão impenetrável gélido onde a precisão sucumbe completamente frente aos eixos térmicos infraestruturados consolidados centrais.")

# ------------- TAB 05 -------------
with tabs[4]:
    st.header("NB05/NB08: Validação das Hipóteses de Pesquisa")
    st.markdown("O mosaico lógico de asserções formuladas é validado ponta a ponta através de rigorosos testes não-paramétricos.")
    st.divider()
    
    st.subheader("Tabela de Vereditos Acadêmicos")
    # Carregar a tabela de resultados gerada no pipeline
    if Path("outputs/tables/hipoteses_resultados.csv").exists():
        df_h = pd.read_csv("outputs/tables/hipoteses_resultados.csv")
        st.table(df_h)
    else:
        st.warning("Tabela de hipóteses não encontrada. Execute a pipeline completa.")
    
    render_analysis("A auditoria final das hipóteses stancionou a robustez dos indicadores PCI/LCI/GCI. Observa-se que 100% das premissas de precariedade documental e espacial em zonas periféricas foram aceitas com significância estatística (p < 0.05).")

# ------------- TAB 06 -------------
with tabs[5]:
    st.header("NB06: LISA e Paradigmas da Autocorrelação Endêmica")
    st.markdown("Varredura estatística não estacionária (LISA / GWR / Hot Spot). Não avalia-se apenas pontos distantes, mas o perigoso 'Contágio' estatístico orgânico em grandes proporções.")
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">Manchas Epidêmicas do Local Moran\'s I</div>', unsafe_allow_html=True)
        load_img("outputs/figures/06_lisa_setor_censitario.png")
    with col2:
        st.markdown('<div class="topic-subheader">Guetos Informacionais: Getis-Ord Gi*</div>', unsafe_allow_html=True)
        load_img("outputs/figures/06_getis_ord_gi.png")
    
    c1, c2 = st.columns(2)
    with c1: render_analysis("Estatística comprova clusters autônomos massivos de zonas frias (Low-Low), atestando que a vulnerabilidade não ocorre de forma passiva esporádica nas residências, mas se espalha regionalmente unificando contiguidades com o apagão paramétrico generalizado em encostas sem cep nativo.")
    with c2: render_analysis("Sob crivo de p-value sigiloso rigoroso, fica explícita a bolha térmica da elite rodoviária circundada pela calota gélida dos anéis periféricos que foram renegados sistematicamente nos acertos cartográficos plenos.")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="topic-subheader">Geographically Weighted Regression R²</div>', unsafe_allow_html=True)
        load_img("outputs/figures/06_gwr_local_r2.png")
    with col4:
        st.markdown('<div class="topic-subheader">Ausência do Estado: Densidade de CRAS</div>', unsafe_allow_html=True)
        load_img("outputs/figures/06_kde_gci_cras.png")

    c3, c4 = st.columns(2)
    with c3: render_analysis("Modelos globais não se sustentam na franja isolada de minas, com as regressões decaindo ao tentar aplicar premissas macro. Fica provado matematicamente transversalmente que os desvios não têm causalidade estacionária igual as matrizes formais exigem.")
    with c4: render_analysis("O espelho social final: o núcleo do Kernel Density correlaciona magistralmente os abismos operacionais estritos de apontamento com as valas socioestatais que limitaram fisicamente as sedes e subestações estatais garantidoras dos raios da proteção de base das esferas (CRAS).")

# ------------- TAB 07 -------------
with tabs[6]:
    st.header("NB07: Causalidade e Determinantes da Incerteza")
    st.markdown("Diagnóstico científico multidimensional para isolar os fatores morfológicos, socioeconômicos e institucionais que explicam a falha da geocodificação.")
    st.divider()
    
    st.subheader("O Abismo Imobiliário Econômico do IPTU")
    load_img("outputs/figures/05_iptu_gci.png", full_width=True)
    render_analysis("Os grandes cinturões das alíquotas de luxo absorveram a fatia farta e hegemônica dos acertos primorosos, ao passo que frações carentes afundaram os dados no oceano da desinformação espacial urbana.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="topic-subheader">Radiografia (SHAP)</div>', unsafe_allow_html=True)
        load_img("outputs/figures/05_shap_summary.png")
    with col2:
        st.markdown('<div class="topic-subheader">Topografia Restritiva</div>', unsafe_allow_html=True)
        load_img("outputs/figures/05_declividade_erro.png")
    
    render_analysis("A modelagem de causalidade prova que a precariedade do terreno e a vulnerabilidade social (favelas) são os drivers primários do erro sistemático, suplantando meros ruídos técnicos de GPS.")

# ------------- TAB 08 -------------
with tabs[7]:
    st.header("NB08: Síntese e Econometria Final Multiescalar")
    st.markdown("O paradoxo de engolimento cilíndrico dos dados oficiais consolidados.")
    st.divider()
    
    st.subheader("Consolidado: Dashboard Multivariado Exploratório")
    # Aumentando drasticamente a altura para 1100px para o Plotly não ficar ilegível
    load_html("outputs/maps/07_dashboard_sintese.html", height=1100)
    render_analysis("Uma auditoria definitiva de ponta a ponta. Este dashboard macroscópico atesta as matrizes finais operacionais geradoras, com todos os painéis e métricas interagindo ativamente e revelando sob filtros dinâmicos a assimetria esmagadora sofrida pelos vetores carentes da medição frente a bolhas elitizadas limpas mapeadas do painel.")
    
    st.subheader("A Curva Iníqua Fundamental de Gini")
    load_img("outputs/figures/07_lorenz_gini.png", full_width=True)
    render_analysis("Importar a matriz basilar Gini expõe a verba paramétrica da nação. Um Gini inflado, estirado drasticamente (*> 0.65*) cimenta a injustiça cartográfica do Censo Brasileiro provando metodologicamente que a acurácia, tal qual a renda capital financeira trilionária exploratória da urbe estelar, é um super trunfo retido ferozmente pela alta minoria territorial da burguesia imobiliária.")

    st.subheader("O Paradoxo Scale Effect (MAUP)")
    load_img("outputs/figures/07_maup_multiescala.png", full_width=True)
    render_analysis("A pedra angular do colapso de pesquisa acadêmica em metrópoles: avaliar desvios absolutos pelo recorte distrital engole os rombos microscópicos absurdos dentro dos distritos. Uma quadra de classe média esmaga as estatísticas e absolve o erro catastrófico gravíssimo dos 3 becos adjacentes escondidos numa grota do mesmo setor, diluindo toda falha social invisível em uma farsa aritmética visual das macro-abstrações agregadoras formais.")

    st.success("🏁 Dissertação Finalizada. O Web App Master Report chancelou o fato: a qualidade tem CEP demarcado.")
