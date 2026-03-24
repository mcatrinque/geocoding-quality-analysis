"""
spatial.py — Análises Geoespaciais: Spider Maps, LISA, Visualizações Cartográficas
"""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import LineString
import contextily as ctx


def generate_spider_map(gdf, geom_cnefe='geometry', geom_bhmap='bhmap_geom',
                        color_col='GCI', sample_n=1000, seed=42,
                        ax=None, basemap=True, title=None, output_path=None):
    """
    Spider Map: linhas conectando CNEFE → BHMap (Gold Standard).
    Cor e opacidade proporcionais ao GCI ou erro.

    Args:
        gdf: GeoDataFrame com ambas as geometrias
        geom_cnefe: Coluna da geometria CNEFE
        geom_bhmap: Coluna da geometria BHMap
        color_col: Coluna para colorir as linhas
        sample_n: Tamanho da amostra (para performance)
        seed: Seed para reprodutibilidade
        ax: Matplotlib Axes (opcional)
        basemap: Adicionar basemap contextily
        title: Título do mapa
        output_path: Caminho para salvar PNG

    Returns:
        fig, ax
    """
    # Sample
    if len(gdf) > sample_n:
        gdf_sample = gdf.sample(n=sample_n, random_state=seed)
    else:
        gdf_sample = gdf

    # Build lines
    lines = []
    colors = []
    for _, row in gdf_sample.iterrows():
        try:
            p1 = row[geom_cnefe]
            p2 = row[geom_bhmap]
            if p1 is not None and p2 is not None and not p1.is_empty and not p2.is_empty:
                lines.append(LineString([p1, p2]))
                colors.append(row.get(color_col, 0.5))
        except Exception:
            continue

    if not lines:
        return None, None

    gdf_lines = gpd.GeoDataFrame({'geometry': lines, color_col: colors},
                                  crs=gdf.crs)

    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 12))
    else:
        fig = ax.figure

    gdf_lines.plot(ax=ax, column=color_col, cmap='RdYlGn', linewidth=0.6,
                   alpha=0.7, legend=True,
                   legend_kwds={'label': color_col, 'shrink': 0.6})

    if basemap:
        try:
            gdf_web = gdf_lines.to_crs(epsg=3857)
            ax.set_xlim(gdf_web.total_bounds[[0, 2]])
            ax.set_ylim(gdf_web.total_bounds[[1, 3]])
            # Re-plot in Web Mercator for basemap
            ax.clear()
            gdf_web.plot(ax=ax, column=color_col, cmap='RdYlGn', linewidth=0.6,
                         alpha=0.7, legend=True,
                         legend_kwds={'label': color_col, 'shrink': 0.6})
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
        except Exception:
            pass

    ax.set_title(title or 'Spider Map: Deslocamento CNEFE → BHMap', fontsize=14)
    ax.axis('off')

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')

    return fig, ax


def plot_hexbin_metric(gdf, metric_col, title=None, cmap='viridis',
                       gridsize=60, basemap=True, output_path=None):
    """
    Hexbin map de uma métrica sobre o território.

    Args:
        gdf: GeoDataFrame com geometria de pontos
        metric_col: Coluna com a métrica (GCI, LCI, etc.)
        title: Título
        cmap: Colormap
        gridsize: Resolução do hexbin
        basemap: Adicionar contextily basemap
        output_path: Caminho de salvamento
    """
    # Convert to Web Mercator for basemap
    gdf_web = gdf.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(14, 12))

    hb = ax.hexbin(
        gdf_web.geometry.x, gdf_web.geometry.y,
        C=gdf_web[metric_col].values,
        reduce_C_function=np.mean,
        gridsize=gridsize, cmap=cmap, mincnt=5
    )

    cb = plt.colorbar(hb, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label(metric_col, fontsize=12)

    if basemap:
        try:
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
        except Exception:
            pass

    ax.set_title(title or f'Distribuição Espacial: {metric_col}', fontsize=14)
    ax.axis('off')

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')

    return fig, ax


def analyze_lisa(gdf, metric_col='GCI', k_neighbors=8, seed=42):
    """
    LISA — Local Indicator of Spatial Association.

    Args:
        gdf: GeoDataFrame com geometria e métrica
        metric_col: Coluna da métrica
        k_neighbors: Número de vizinhos para matriz de pesos

    Returns:
        moran_loc: Objeto Moran_Local
        gdf: GeoDataFrame com coluna 'lisa_cluster' adicionada
    """
    import libpysal
    from esda.moran import Moran, Moran_Local

    np.random.seed(seed)

    # Ensure we have valid geometries and no NaN in metric
    gdf_valid = gdf[gdf.geometry.is_valid & gdf[metric_col].notna()].copy()

    # Build spatial weights
    weights = libpysal.weights.KNN.from_dataframe(gdf_valid, k=k_neighbors)
    weights.transform = 'r'

    # Global Moran
    moran_global = Moran(gdf_valid[metric_col], weights)

    # Local Moran
    moran_loc = Moran_Local(gdf_valid[metric_col], weights, seed=seed)

    # Classify clusters
    sig = moran_loc.p_sim < 0.05
    quadrants = moran_loc.q  # 1=HH, 2=LH, 3=LL, 4=HL
    cluster_labels = ['Not Significant'] * len(gdf_valid)
    for i in range(len(gdf_valid)):
        if sig[i]:
            if quadrants[i] == 1:
                cluster_labels[i] = 'High-High'
            elif quadrants[i] == 2:
                cluster_labels[i] = 'Low-High'
            elif quadrants[i] == 3:
                cluster_labels[i] = 'Low-Low'
            elif quadrants[i] == 4:
                cluster_labels[i] = 'High-Low'

    gdf_valid['lisa_cluster'] = cluster_labels

    return moran_global, moran_loc, gdf_valid
