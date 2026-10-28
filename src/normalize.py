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


def partes_endereco(consulta):
    """Separa uma consulta livre em logradouro, número e pistas territoriais.

    O endereço digitado costuma vir com bairro e cidade depois do número, e
    tratá-los como parte do nome da via faz a busca por similaridade casar com
    o logradouro errado. A separação por vírgula ou travessão isola o nome da
    via; o número é procurado nos campos seguintes e, se não estiver lá, no fim
    do primeiro campo. O que sobra vira pista para desempatar homônimos.

    Ex.: 'Rua da Bahia, 1000, Centro, Belo Horizonte'
         -> ('RUA DA BAHIA', '1000', ['CENTRO', 'BELO HORIZONTE'])
    """
    if consulta is None:
        return '', None, []

    campos = [c.strip() for c in re.split(r'[,;]| - ', str(consulta)) if c and c.strip()]
    if not campos:
        return '', None, []

    logradouro = normalize_logradouro(campos[0])
    numero = None
    pistas = []

    for campo in campos[1:]:
        so_numero = re.fullmatch(r'(?:N[ºO°]?\.?\s*)?(\d{1,6})\s*([A-Za-z]?)',
                                 campo.strip(), flags=re.IGNORECASE)
        if so_numero and numero is None:
            numero = str(int(so_numero.group(1))) + so_numero.group(2).upper()
        else:
            pista = normalize_logradouro(campo)
            if pista:
                pistas.append(pista)

    # Número colado ao fim do nome da via ('Rua X 100'), com ou sem vírgula
    final = re.search(r'(\d+)\s*([A-Z]?)\s*$', logradouro)
    if numero is None and final and final.start() > 0:
        numero = str(int(final.group(1))) + final.group(2)
        logradouro = logradouro[: final.start()].strip()

    return logradouro, numero, pistas


def split_logradouro_numero(consulta):
    """Compatibilidade: devolve apenas o logradouro canônico e o número."""
    logradouro, numero, _ = partes_endereco(consulta)
    return logradouro, numero


# Tipos de logradouro reconhecidos, para separar o tipo do nome da via. A
# separação em componentes é o que permite conciliar fontes que escrevem o mesmo
# logradouro de formas diferentes, e é pré-requisito da conflação multifonte.
TIPOS_CANONICOS = sorted(set(TIPOS.values()), key=len, reverse=True)


def separar_tipo_logradouro(logradouro):
    """Separa o logradouro canônico em (tipo, nome).

    Ex.: 'AVENIDA AFONSO PENA' -> ('AVENIDA', 'AFONSO PENA').
    Quando o primeiro termo não é um tipo reconhecido, o tipo volta como None e
    o nome recebe o logradouro inteiro, sem perda de informação.
    """
    if not logradouro:
        return None, logradouro
    texto = str(logradouro).strip()
    for tipo in TIPOS_CANONICOS:
        if texto.startswith(tipo + ' '):
            return tipo, texto[len(tipo) + 1:].strip()
    return None, texto


def normalize_cep(valor):
    """CEP em oito dígitos, ou None quando não houver CEP válido.

    Aceita as formas com hífen, com ponto e com espaços. Valores com menos de
    oito dígitos, ou compostos apenas de zeros, são descartados em vez de
    armazenados como se fossem válidos.
    """
    if valor is None:
        return None
    digitos = re.sub(r'\D', '', str(valor))
    if len(digitos) != 8 or digitos == '0' * 8:
        return None
    return digitos
