"""Normalização canônica de endereços do repositório de referência.

Define uma forma canônica única para o logradouro, aplicada tanto na ingestão
(garantindo consistência entre fontes) quanto na consulta da API (tornando a
busca robusta a abreviações, acentos e caixa). O CNEFE 2022 já chega quase
canônico (tipo por extenso, sem acento, maiúsculas), mas fontes futuras como o
BHMap e o OSM não, e o usuário digita de forma livre.
"""
import re
import unicodedata

# Tipos de logradouro: abreviações -> forma canônica (sem acento, como o CNEFE).
TIPOS = {
    "R": "RUA", "RUA": "RUA",
    "AV": "AVENIDA", "AVE": "AVENIDA", "AVEN": "AVENIDA", "AVENIDA": "AVENIDA",
    "AL": "ALAMEDA", "ALA": "ALAMEDA", "ALAMEDA": "ALAMEDA",
    "PC": "PRACA", "PCA": "PRACA", "PRC": "PRACA", "PÇA": "PRACA", "PRACA": "PRACA",
    "TV": "TRAVESSA", "TRV": "TRAVESSA", "TRAV": "TRAVESSA", "TRAVESSA": "TRAVESSA",
    "ROD": "RODOVIA", "RODOVIA": "RODOVIA",
    "EST": "ESTRADA", "ESTR": "ESTRADA", "ESTRADA": "ESTRADA",
    "BC": "BECO", "BECO": "BECO",
    "LGO": "LARGO", "LARGO": "LARGO",
    "VD": "VIADUTO", "VIADUTO": "VIADUTO",
    "PSG": "PASSAGEM", "PASSAGEM": "PASSAGEM",
    "VIA": "VIA",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_logradouro(s) -> str:
    """Forma canônica do logradouro: sem acento, maiúsculo, sem pontuação,
    espaços colapsados e tipo de logradouro por extenso."""
    if s is None:
        return s
    s = strip_accents(str(s)).upper()
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return s
    parts = s.split(" ")
    tipo = TIPOS.get(parts[0])
    if tipo and len(parts) > 1:
        parts[0] = tipo
    return " ".join(parts)


def split_logradouro_numero(consulta: str):
    """Separa uma consulta livre em (logradouro canônico, número), extraindo o
    número final quando presente. Ex.: 'av. afonso pena, 210' -> ('AVENIDA AFONSO PENA', '210')."""
    termo = normalize_logradouro(consulta)
    if not termo:
        return termo, None
    m = re.search(r"(\d+)\s*$", termo)
    if m and m.start() > 0:
        return termo[: m.start()].strip(), m.group(1)
    return termo, None
