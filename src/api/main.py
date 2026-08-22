from collections import Counter

from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from .database import engine, get_db, Base
from .schemas import GeocodeRequest, GeocodeResponse, ReverseRequest, ReverseResponse
from ..normalize import split_logradouro_numero

# Plus Code (Open Location Code). Se a lib não estiver instalada, a resposta
# simplesmente omite o campo em vez de falhar.
try:
    from openlocationcode import openlocationcode as _olc

    def plus_code(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        if lat is None or lon is None:
            return None
        try:
            return _olc.encode(lat, lon)
        except Exception:
            return None
except Exception:
    def plus_code(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        return None


def classe_confianca(gci: Optional[float]) -> Optional[str]:
    """Traduz o GCI em uma classe de confiança acionável (confiança delimitada)."""
    if gci is None:
        return None
    if gci >= 0.8:
        return "alta"
    if gci >= 0.5:
        return "moderada"
    return "baixa"


app = FastAPI(
    title="Geocoding Quality PoC",
    description="Prova de conceito de geocodificador com indicação empírica de qualidade",
    version="1.2.0",
)

# Contabilização de uso (metering): conta requisições por rota em memória.
_usage = Counter()


@app.middleware("http")
async def meter(request: Request, call_next):
    _usage[request.url.path] += 1
    return await call_next(request)


@app.get("/")
def read_root():
    return {"message": "API de Geocodificação (PoC) online. Utilize /docs para ver a documentação."}


@app.get("/usage")
def usage():
    """Contabilização de uso da API: total de requisições e contagem por rota."""
    return {"total": sum(_usage.values()), "por_rota": dict(_usage)}


@app.post("/geocode", response_model=List[GeocodeResponse])
def geocode(request: GeocodeRequest, db: Session = Depends(get_db)):
    """
    Geocodifica um endereço. A consulta é normalizada para a forma canônica do
    repositório (expande abreviações, remove acentos), o que torna a busca
    robusta a como o usuário digita. Devolve a coordenada com a fonte, o Plus
    Code, os indicadores de qualidade e a classe de confiança.
    """
    termo_log, numero = split_logradouro_numero(request.endereco)
    if not termo_log:
        raise HTTPException(status_code=400, detail="Consulta vazia após normalização.")

    query = text("""
        SELECT
            e.logradouro, e.numero, e.latitude, e.longitude,
            e.lci, e.mci, e.cdi, e.gci, e.n_unidades, f.nome as fonte
        FROM endereco e
        JOIN fonte f ON e.id_fonte = f.id_fonte
        WHERE similarity(e.logradouro, :termo_log) >= 0.30
        ORDER BY
            (CASE WHEN :numero <> '' AND e.numero = :numero THEN 0 ELSE 1 END),
            similarity(e.logradouro, :termo_log) DESC
        LIMIT 5;
    """)

    result = db.execute(query, {
        "termo_log": termo_log,
        "numero": numero or "",
    }).fetchall()

    if not result:
        raise HTTPException(status_code=404, detail="Endereço não encontrado no repositório.")

    respostas = []
    for row in result:
        endereco_str = row.logradouro
        if row.numero:
            endereco_str += f", {row.numero}"
        lat = float(row.latitude) if row.latitude is not None else 0.0
        lon = float(row.longitude) if row.longitude is not None else 0.0
        gci = float(row.gci) if row.gci is not None else None
        respostas.append(GeocodeResponse(
            endereco_encontrado=endereco_str,
            fonte=row.fonte,
            latitude=lat,
            longitude=lon,
            plus_code=plus_code(lat, lon),
            confianca=classe_confianca(gci),
            gci_empirico=gci,
            cdi=int(row.cdi) if row.cdi is not None else None,
            lci=float(row.lci) if row.lci is not None else None,
            mci=float(row.mci) if row.mci is not None else None,
            n_unidades=int(row.n_unidades) if row.n_unidades is not None else None,
        ))
    return respostas


@app.post("/reverse", response_model=ReverseResponse)
def reverse(request: ReverseRequest, db: Session = Depends(get_db)):
    """
    Geocodificação reversa: dada uma coordenada, devolve o endereço mais próximo
    no repositório, com a distância em metros, a classe de confiança e os
    indicadores de qualidade.
    """
    query = text("""
        SELECT
            e.logradouro, e.numero, e.latitude, e.longitude,
            e.lci, e.mci, e.cdi, e.gci, e.n_unidades, f.nome as fonte,
            ST_Distance(
                e.geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) AS dist_m
        FROM endereco e
        JOIN fonte f ON e.id_fonte = f.id_fonte
        ORDER BY e.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 1;
    """)

    row = db.execute(query, {"lat": request.latitude, "lon": request.longitude}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Nenhum endereço próximo encontrado.")

    endereco_str = row.logradouro
    if row.numero:
        endereco_str += f", {row.numero}"
    lat = float(row.latitude) if row.latitude is not None else 0.0
    lon = float(row.longitude) if row.longitude is not None else 0.0
    gci = float(row.gci) if row.gci is not None else None

    return ReverseResponse(
        endereco_encontrado=endereco_str,
        fonte=row.fonte,
        latitude=lat,
        longitude=lon,
        plus_code=plus_code(lat, lon),
        confianca=classe_confianca(gci),
        distancia_m=float(row.dist_m) if row.dist_m is not None else None,
        gci_empirico=gci,
        cdi=int(row.cdi) if row.cdi is not None else None,
        lci=float(row.lci) if row.lci is not None else None,
        mci=float(row.mci) if row.mci is not None else None,
        n_unidades=int(row.n_unidades) if row.n_unidades is not None else None,
    )
