"""Contratos de entrada e saída da API do repositório de endereços."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NivelPrecisao(str, Enum):
    """Até onde a consulta casou com o repositório.

    A distinção é o que separa uma resposta útil de uma resposta enganosa: um
    geocodificador que devolve coordenada para tudo, sem dizer em que nível
    casou, transfere ao usuário um erro que ele não tem como perceber.
    """

    NUMERO_EXATO = 'numero_exato'
    NUMERO_APROXIMADO = 'numero_aproximado'
    LOGRADOURO = 'logradouro'
    PROXIMIDADE = 'proximidade'


class ClasseConfianca(str, Enum):
    ALTA = 'alta'
    MODERADA = 'moderada'
    BAIXA = 'baixa'


class StatusCalibracao(str, Enum):
    """Indica se há estimativa elegível para esta rota, política e versão de dados."""

    CALIBRADA = 'calibrada'
    DECLARADA = 'declarada'


class Calibracao(BaseModel):
    """O que a classe de confiança significa em metros, quando isso foi medido."""

    status: StatusCalibracao = Field(
        ..., description='calibrada: há teste independente vinculado à política e aos dados; '
                         'declarada: não há estimativa elegível para esta resposta')
    referencia: Optional[str] = Field(
        None, description='Base e amostra contra as quais o erro foi medido')
    base: Optional[str] = Field(
        None, description='Granularidade da estimativa: nivel+confianca, nivel ou global. '
                          'Recua quando a célula tem casos de menos para sustentar quantil')
    n_amostra: Optional[int] = Field(
        None, description='Casos medidos na granularidade usada')
    erro_mediano_m: Optional[float] = Field(
        None, description='Erro mediano observado nesta classe, em metros')
    erro_ce90_m: Optional[float] = Field(
        None, description='Percentil 90 do erro observado na amostra, não garantia individual')
    acima_de_30_m_pct: Optional[float] = Field(
        None, description='Percentual desta classe com erro acima de 30 m')
    acima_de_100_m_pct: Optional[float] = Field(
        None, description='Percentual desta classe com erro grosseiro, acima de 100 m')
    versao_dados: Optional[str] = None
    versao_politica: Optional[str] = None
    tipo_consulta: Optional[str] = None
    amostra: Optional[str] = None


class GeocodeRequest(BaseModel):
    endereco: str = Field(..., min_length=2, max_length=300,
                          description="Endereço a geocodificar. Ex: 'Av. Afonso Pena, 210'")
    municipio: Optional[str] = Field(
        None, max_length=100,
        description='Recorte por município. Sem ele, a busca varre todo o repositório, '
                    'o que é ambíguo quando há mais de um município carregado')
    uf: Optional[str] = Field(None, min_length=2, max_length=2,
                              description='Sigla da unidade federativa, ex: MG')
    bairro: Optional[str] = Field(
        None, max_length=100,
        description='Bairro, usado para desempatar logradouros homônimos. '
                    'Quando o bairro vem no próprio texto do endereço, é aproveitado')
    codigo_municipio: Optional[str] = Field(
        None, min_length=7, max_length=7,
        description='Código IBGE do município. Tem precedência sobre municipio e uf')
    limite: int = Field(5, ge=1, le=20, description='Número máximo de candidatos')


class ReverseRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    raio_m: float = Field(200.0, gt=0, le=5000,
                          description='Raio máximo de busca, em metros')


class Qualidade(BaseModel):
    """Indicadores de resposta com evidência empírica separada no campo calibração."""

    confianca_posicional: ClasseConfianca = Field(
        ..., description='Classe heurística da correspondência: alta, moderada ou baixa')
    incerteza_identidade: Optional[ClasseConfianca] = Field(
        None, description='Classe heurística de duplicação de coordenadas pelo CDI. '
                          'Não é probabilidade validada de identidade correta')
    calibracao: Calibracao = Field(
        ..., description='Evidência de teste independente contra referência de comparação, '
                         'vinculada à política e aos dados em execução')
    motivo: str = Field(..., description='O que determinou as classes, em texto legível')
    gci_empirico: Optional[float] = Field(None, description='Índice experimental LCI x MCI x 1/CDI, dependente de referência externa')
    lci: Optional[float] = Field(None, description='Certeza do método de coleta da fonte')
    mci: Optional[float] = Field(None, description='Certeza do pareamento com a referência externa')
    cdi: Optional[int] = Field(None, description='Registros da fonte compartilhando a coordenada')
    dispersao_m: Optional[float] = Field(
        None, description='Discordância, em metros, entre as coordenadas consolidadas neste endereço')
    n_unidades: Optional[int] = Field(None, description='Registros de origem agrupados, sem comprovação de unidades distintas')


class EnderecoResposta(BaseModel):
    endereco_encontrado: str
    codigo_municipio: Optional[str] = Field(None, description='Código IBGE do município do candidato')
    logradouro: str
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    fonte: str
    versao_fonte: Optional[str] = Field(None, description='Versão declarada pela carga da fonte')
    versao_dados: Optional[str] = Field(
        None, description='SHA256 da identidade do conjunto carregado, com fonte, município, '
                          'versão, arquivos de entrada e processamento. Ausente sem manifesto')
    latitude: float
    longitude: float
    plus_code: Optional[str] = None
    nivel_precisao: NivelPrecisao
    similaridade_logradouro: Optional[float] = Field(
        None, description='Similaridade textual na geocodificação direta. Ausente na reversa')
    diferenca_numero: Optional[int] = Field(
        None, description='Diferença de numeração quando o nível é numero_aproximado')
    qualidade: Qualidade


class ReverseResposta(EnderecoResposta):
    distancia_m: float = Field(..., description='Distância entre a coordenada consultada e o endereço')


class GeocodeResultado(BaseModel):
    consulta: str
    logradouro_normalizado: str
    numero_consultado: Optional[str] = None
    total: int
    candidatos: List[EnderecoResposta]


class Cobertura(BaseModel):
    codigo_municipio: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    fonte: str
    enderecos: int
    unidades: int


class Saude(BaseModel):
    status: str
    banco: str
    enderecos: int
    municipios: int
    versao: str


class UsoPorRota(BaseModel):
    rota: str
    requisicoes: int
    latencia_media_ms: Optional[float] = None
    erros: int


class UsoResultado(BaseModel):
    desde: Optional[str] = None
    total: int
    por_rota: List[UsoPorRota]
    por_cliente: dict
    telemetria_descartada_processo: int = Field(
        0, description='Eventos perdidos no processo que respondeu, incluindo fila cheia e falha de gravação')
    telemetria_pendente_processo: int = Field(
        0, description='Eventos ainda na fila deste processo')
    limite_por_minuto_processo: int = Field(
        0, description='Limite por cliente em cada processo. Zero significa desativado')
