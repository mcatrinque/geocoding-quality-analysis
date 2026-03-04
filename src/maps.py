import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
import contextily as cx
import os
from pathlib import Path

def plot_kde_heatmap(
    gdf: gpd.GeoDataFrame, 
    output_path: str = None, 
    title: str = "Spatial Uncertainty Heatmap",
    cmap: str = "YlOrRd",
    alpha: float = 0.6,
    figsize: tuple = (12, 12),
    add_basemap: bool = True
):
    """
    Plots a Kernel Density Estimate (KDE) heatmap of the points in a GeoDataFrame.
    Usually used to map low MCI or high positional error areas.
    """
    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)
    
    # Ensure CRS is Web Mercator (EPSG:3857) for contextily if adding a basemap
    if add_basemap and gdf.crs != "EPSG:3857":
        plot_gdf = gdf.to_crs(epsg=3857)
    else:
        plot_gdf = gdf

    # Extract X and Y for Seaborn KDE
    x = plot_gdf.geometry.x
    y = plot_gdf.geometry.y

    # Plot the KDE Heatmap overlaid on the axis
    sns.kdeplot(
        x=x, y=y,
        cmap=cmap,
        fill=True,
        alpha=alpha,
        levels=20,
        ax=ax
    )
    
    # Optional: plot the actual points as small dots
    # plot_gdf.plot(ax=ax, markersize=1, color='black', alpha=0.1)

    if add_basemap:
        try:
            cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)
        except Exception as e:
            print(f"Warning: Could not add basemap. {e}")

    # Remove axes for map style
    ax.set_axis_off()
    ax.set_title(title, fontsize=16, fontweight='bold')

    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved heatmap to {output_path}")
        
    return fig, ax

def plot_completeness_bar_chart(
    completeness_df, 
    output_path: str = None,
    title: str = "Attribute Completeness (%)"
):
    """
    Plots a horizontal bar chart showing the completeness percentage of attributes.
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
    
    # Add percentage labels to the bars
    for i, v in enumerate(completeness_df['Completeness (%)']):
        ax.text(v + 1, i, f"{v:.1f}%", color='black', va='center')
        
    sns.despine(left=True, bottom=True)
    plt.tight_layout()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved bar chart to {output_path}")
        
    return fig, ax
