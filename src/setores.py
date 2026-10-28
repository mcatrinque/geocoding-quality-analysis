"""Setores censitários da malha preliminar do Censo 2022, na codificação do CNEFE."""
import geopandas as gpd

from src import config


def carregar_setores_preliminares():
    """Setores de Belo Horizonte em EPSG:31983, indexados pelo código com o sufixo P, como no CNEFE."""
    s = gpd.read_file(config.SETOR_PRELIMINAR_GPKG, where=f"CD_MUN='{config.COD_MUNICIPIO_BH}'")
    s = s[['CD_SETOR', 'AREA_KM2', 'NM_SUBDIST', 'geometry']].to_crs(config.TARGET_CRS)
    assert s.CD_SETOR.is_unique
    return s.set_index('CD_SETOR')
