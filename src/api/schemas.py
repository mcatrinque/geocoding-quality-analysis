from pydantic import BaseModel, Field
from typing import Optional


class GeocodeRequest(BaseModel):
    endereco: str = Field(..., description="O endereço a ser geocodificado. Ex: 'Av. Afonso Pena, 210'")


class ReverseRequest(BaseModel):
    latitude: float = Field(..., description="Latitude da coordenada consultada (WGS84).")
    longitude: float = Field(..., description="Longitude da coordenada consultada (WGS84).")


class GeocodeResponse(BaseModel):
    endereco_encontrado: str
    fonte: str
    latitude: float
    longitude: float
    plus_code: Optional[str] = Field(None, description="Open Location Code (Plus Code) da coordenada")
    # Indicadores de qualidade (confiança delimitada)
    confianca: Optional[str] = Field(None, description="Classe de confiança: alta, moderada ou baixa")
    gci_empirico: Optional[float] = Field(None, description="Global Certainty Index (calibrado empiricamente)")
    cdi: Optional[int] = Field(None, description="Coordinate Duplication Index (incerteza de identidade)")
    lci: Optional[float] = Field(None, description="Location Certainty Index (certeza de coleta)")
    mci: Optional[float] = Field(None, description="Match Certainty Index")
    n_unidades: Optional[int] = Field(None, description="Unidades que compartilham esta coordenada")


class ReverseResponse(GeocodeResponse):
    distancia_m: Optional[float] = Field(
        None, description="Distância entre a coordenada consultada e o endereço encontrado, em metros"
    )
