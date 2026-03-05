"""
Módulo de visualização cartográfica.

Fornece funções de plotagem para heatmaps KDE e gráficos de barras
de completude, usando Matplotlib, Seaborn e Contextily.
"""

from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
import contextily as cx
from matplotlib.figure import Figure
from matplotlib.axes import Axes


def plot_kde_heatmap(
    gdf: gpd.GeoDataFrame,
    output_path: Optional[str] = None,
    title: str = "Spatial Uncertainty Heatmap",
    cmap: str = "YlOrRd",
    alpha: float = 0.6,
    figsize: tuple = (12, 12),
    add_basemap: bool = True
) -> Tuple[Figure, Axes]:
    """
    Plota um mapa de calor KDE (Kernel Density Estimate) dos pontos de um GeoDataFrame.

    Geralmente utilizado para mapear áreas de baixo MCI ou alto erro posicional.

    Args:
        gdf: GeoDataFrame com geometria de pontos.
        output_path: Caminho para salvar a imagem (opcional).
        title: Título do gráfico.
        cmap: Paleta de cores do mapa de calor.
        alpha: Transparência da camada KDE.
        figsize: Dimensões da figura em polegadas.
        add_basemap: Se True, adiciona basemap do CartoDB via Contextily.

    Returns:
        Tupla (Figure, Axes) do Matplotlib.
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Reprojetar para Web Mercator (EPSG:3857) se necessário para o basemap
    if add_basemap and gdf.crs != "EPSG:3857":
        plot_gdf = gdf.to_crs(epsg=3857)
    else:
        plot_gdf = gdf

    x = plot_gdf.geometry.x
    y = plot_gdf.geometry.y

    sns.kdeplot(
        x=x, y=y,
        cmap=cmap,
        fill=True,
        alpha=alpha,
        levels=20,
        ax=ax
    )

    if add_basemap:
        try:
            cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
        except Exception as e:
            print(f"Warning: Could not add basemap. {e}")

    ax.set_axis_off()
    ax.set_title(title, fontsize=16, fontweight='bold')
    plt.tight_layout()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved heatmap to {output_path}")

    return fig, ax


def plot_completeness_bar_chart(
    completeness_df: "pd.DataFrame",
    output_path: Optional[str] = None,
    title: str = "Attribute Completeness (%)"
) -> Tuple[Figure, Axes]:
    """
    Plota um gráfico de barras horizontais com a porcentagem de completude dos atributos.

    Args:
        completeness_df: DataFrame com colunas 'Attribute' e 'Completeness (%)'.
        output_path: Caminho para salvar a imagem (opcional).
        title: Título do gráfico.

    Returns:
        Tupla (Figure, Axes) do Matplotlib.
    """
    completeness_df = completeness_df.sort_values(by='Completeness (%)', ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=completeness_df,
        x='Completeness (%)',
        y='Attribute',
        palette='viridis',
        ax=ax
    )

    ax.set_xlim(0, 100)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel("Completeness (%)")
    ax.set_ylabel("")

    for i, v in enumerate(completeness_df['Completeness (%)']):
        ax.text(v + 1, i, f"{v:.1f}%", color='black', va='center')

    sns.despine(left=True, bottom=True)
    plt.tight_layout()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved bar chart to {output_path}")

    return fig, ax
