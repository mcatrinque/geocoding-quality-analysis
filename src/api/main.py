"""API de prova de conceito do repositório de endereços de referência.

A resposta declara o tipo de correspondência, a fonte e os indicadores
disponíveis. Estimativas de erro só são expostas para amostras independentes
vinculadas à política e à versão dos dados em execução.
"""

import hashlib
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import engine, get_db
from .calibracao import identificar_versao_dados, obter_calibrador
from .enriquecimento import obter_enriquecedor
from .metering import Contabilizador, LimitadorDeTaxa, Registro, clientes_configurados
from .schemas import (Calibracao, ClasseConfianca, Cobertura, EnderecoResposta,
                      GeocodeRequest, GeocodeResultado, NivelPrecisao, Qualidade,
                      ReverseRequest, ReverseResposta, Saude, StatusCalibracao,
                      UsoPorRota, UsoResultado)
from ..normalize import normalize_logradouro

VERSAO = '2.0.0'
logger = logging.getLogger(__name__)

# Limiar de similaridade do pg_trgm. Aplicado por transação, é o que faz o
# operador % usar o índice GIN em vez de varrer a tabela.
LIMIAR_SIMILARIDADE = float(os.environ.get('LIMIAR_SIMILARIDADE', 0.30))

# Acima desta dispersão, as fontes discordam demais sobre onde fica o endereço
# para que a resposta seja apresentada como de alta confiança.
DISPERSAO_ACEITAVEL_M = float(os.environ.get('DISPERSAO_ACEITAVEL_M', 30.0))

# Limiares ajustados em 20.000 endereços do BHMap durante o desenvolvimento.
# Sem eles o serviço respondia a qualquer consulta acima da similaridade mínima
# do pg_trgm, e as respostas de logradouro mal casado, 4,4% do total,
# concentravam 29% dos erros grosseiros, com mediana de 9,3 km.
# Essas observações não constituem teste independente da política.
SIMILARIDADE_MINIMA = float(os.environ.get('SIMILARIDADE_MINIMA', 0.45))
SIMILARIDADE_NUMERO = float(os.environ.get('SIMILARIDADE_NUMERO', 0.65))
SIMILARIDADE_EXATA = float(os.environ.get('SIMILARIDADE_EXATA', 0.90))
DIFERENCA_NUMERO_MAXIMA = int(os.environ.get('DIFERENCA_NUMERO_MAXIMA', 20))
VERSAO_POLITICA = hashlib.sha256(Path(__file__).read_bytes() + repr((
    VERSAO, LIMIAR_SIMILARIDADE, SIMILARIDADE_MINIMA, SIMILARIDADE_NUMERO,
    SIMILARIDADE_EXATA, DIFERENCA_NUMERO_MAXIMA, DISPERSAO_ACEITAVEL_M,
    'geocode-sql-3-sufixo',
)).encode('utf-8')).hexdigest()

ROTAS_LIVRES = {'/health', '/docs', '/redoc', '/openapi.json', '/'}

try:
    from openlocationcode import openlocationcode as _olc

    def plus_code(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        if lat is None or lon is None:
            return None
        try:
            return _olc.encode(lat, lon)
        except Exception:
            return None
except Exception:                                            # pragma: no cover
    def plus_code(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        return None


contabilizador = Contabilizador(engine)
limitador = LimitadorDeTaxa(int(os.environ.get('LIMITE_POR_MINUTO', 0)))

# Tratamento do endereço de entrada. A troca por métodos de inteligência
# artificial é uma troca de implementação, não de rota (ver src/api/enriquecimento.py).
enriquecedor = obter_enriquecedor()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    contabilizador.iniciar()
    try:
        yield
    finally:
        contabilizador.encerrar()


app = FastAPI(
    title='Repositório de endereços de referência',
    description=__doc__,
    version=VERSAO,
    lifespan=ciclo_de_vida,
)


def identificar_cliente(request: Request) -> Optional[str]:
    """Nome do cliente pela chave de API. None quando a chave é exigida e inválida."""
    mapa = clientes_configurados()
    if not mapa:
        return 'anonimo'
    chave = request.headers.get('X-API-Key', '')
    return mapa.get(chave)


@app.middleware('http')
async def medir_e_autenticar(request: Request, call_next):
    inicio = time.perf_counter()
    rota = request.url.path
    cliente = identificar_cliente(request)

    try:
        if cliente is None and rota not in ROTAS_LIVRES:
            resposta = JSONResponse(status_code=401,
                                    content={'detail': 'Chave de API ausente ou inválida.'})
        elif not limitador.permitido(cliente or 'anonimo', int(time.time() // 60)):
            resposta = JSONResponse(
                status_code=429,
                content={'detail': f'Limite de {limitador.limite} requisições por minuto excedido.'})
        else:
            resposta = await call_next(request)
    except Exception:
        contabilizador.registrar(Registro(
            rota=rota[:60], metodo=request.method, status=500,
            latencia_ms=int((time.perf_counter() - inicio) * 1000),
            cliente=(cliente or 'nao_autenticado')[:80],
            resultados=getattr(request.state, 'resultados', None)))
        raise

    latencia = int((time.perf_counter() - inicio) * 1000)
    contabilizador.registrar(Registro(
        rota=rota[:60], metodo=request.method, status=resposta.status_code,
        latencia_ms=latencia, cliente=(cliente or 'nao_autenticado')[:80],
        resultados=getattr(request.state, 'resultados', None),
    ))
    resposta.headers['X-Latencia-ms'] = str(latencia)
    return resposta


def classe_por_gci(gci: Optional[float]) -> ClasseConfianca:
    """Limiares derivados da distribuição empírica do GCI em BH (NB05 e NB13)."""
    if gci is None:
        return ClasseConfianca.BAIXA
    if gci >= 0.8:
        return ClasseConfianca.ALTA
    if gci >= 0.5:
        return ClasseConfianca.MODERADA
    return ClasseConfianca.BAIXA


ORDEM = [ClasseConfianca.BAIXA, ClasseConfianca.MODERADA, ClasseConfianca.ALTA]


def rebaixar(atual: ClasseConfianca, teto: ClasseConfianca) -> ClasseConfianca:
    return atual if ORDEM.index(atual) <= ORDEM.index(teto) else teto


def avaliar_qualidade(linha, nivel: NivelPrecisao, similaridade: Optional[float],
                      diferenca: Optional[int], tipo_consulta: str = 'geocode') -> Qualidade:
    """Declara classes da correspondência e só associa erro observado elegível."""
    gci = None
    cdi = int(linha.cdi) if linha.cdi is not None else None
    dispersao = float(linha.dispersao_m) if linha.dispersao_m is not None else 0.0
    motivos = []

    if tipo_consulta == 'reverse':
        posicional = ClasseConfianca.BAIXA
        motivos.append('endereço candidato mais próximo da coordenada consultada, sem casamento textual')
    elif nivel is NivelPrecisao.NUMERO_EXATO:
        posicional = ClasseConfianca.ALTA
    elif nivel is NivelPrecisao.NUMERO_APROXIMADO:
        posicional = ClasseConfianca.MODERADA
        motivos.append('o número consultado não existe no repositório, a resposta é o mais '
                       f'próximo no mesmo logradouro, a {diferenca} de distância na numeração')
    else:
        posicional = ClasseConfianca.BAIXA
        motivos.append('a resposta identifica o logradouro, não o imóvel')

    if similaridade is not None and similaridade < SIMILARIDADE_NUMERO:
        posicional = rebaixar(posicional, ClasseConfianca.BAIXA)
        motivos.append(f'o logradouro casou mal (similaridade {similaridade:.2f})')
    elif similaridade is not None and similaridade < SIMILARIDADE_EXATA:
        posicional = rebaixar(posicional, ClasseConfianca.MODERADA)
        motivos.append(f'o logradouro casou parcialmente (similaridade {similaridade:.2f})')

    if dispersao > DISPERSAO_ACEITAVEL_M:
        posicional = rebaixar(posicional, ClasseConfianca.MODERADA)
        motivos.append(f'as fontes consolidadas neste endereço discordam em {dispersao:.0f} m')

    if not motivos:
        motivos.append('casamento exato de logradouro e número')

    n_unidades = int(linha.n_unidades) if linha.n_unidades is not None else 1
    if cdi is None:
        identidade = None
    elif cdi <= 2:
        identidade = ClasseConfianca.BAIXA
    elif cdi <= 10:
        identidade = ClasseConfianca.MODERADA
    else:
        identidade = ClasseConfianca.ALTA
        motivos.append(f'{cdi} registros da fonte compartilham esta coordenada, '
                       'essa contagem não identifica unidades físicas')

    codigo_municipio = getattr(linha, 'codigo_municipio', None)
    identificador = identificar_versao_dados(
        getattr(linha, 'fonte', None), codigo_municipio,
        getattr(linha, 'versao_fonte', None), getattr(linha, 'arquivo_sha256', None),
        getattr(linha, 'qualidade_sha256', None),
        getattr(linha, 'processamento_sha256', None))
    calibracao = obter_calibrador().consultar(
        codigo_municipio, nivel, posicional,
        versao_dados=identificador,
        versao_politica=VERSAO_POLITICA, tipo_consulta=tipo_consulta)

    if calibracao.status is StatusCalibracao.CALIBRADA:
        motivos.append(
            f'nesta classe, o erro mediano medido foi de {calibracao.erro_mediano_m:.1f} m '
            f'e o CE90 de {calibracao.erro_ce90_m:.1f} m')
    else:
        calibracao = Calibracao(status=StatusCalibracao.DECLARADA,
                               versao_dados=identificador, versao_politica=VERSAO_POLITICA,
                               tipo_consulta=tipo_consulta)
        motivos.append('não há teste independente vinculado a esta rota, política e versão '
                       'dos dados, então a classe é declarada e não foi verificada aqui')

    return Qualidade(
        confianca_posicional=posicional,
        incerteza_identidade=identidade,
        calibracao=calibracao,
        motivo='. '.join(motivos),
        gci_empirico=gci,
        lci=float(linha.lci) if linha.lci is not None else None,
        mci=float(linha.mci) if linha.mci is not None else None,
        cdi=cdi, dispersao_m=dispersao, n_unidades=n_unidades,
    )


def montar_resposta(linha, numero_consultado: Optional[int],
                    tipo_consulta: str = 'geocode',
                    numero_completo: Optional[str] = None) -> EnderecoResposta:
    """Classifica o nível de precisão segundo os limiares calibrados no NB14."""
    numero_linha = int(linha.numero_norm) if linha.numero_norm is not None else None
    similaridade = float(linha.sim) if tipo_consulta == 'geocode' else None
    diferenca = (abs(numero_linha - numero_consultado)
                 if numero_linha is not None and numero_consultado is not None else None)

    if tipo_consulta == 'reverse':
        nivel = NivelPrecisao.PROXIMIDADE
        diferenca = None
    elif numero_consultado is None:
        nivel = NivelPrecisao.LOGRADOURO
        diferenca = None
    elif (diferenca == 0 and similaridade >= SIMILARIDADE_EXATA
          and str(linha.numero).upper() == (numero_completo or str(numero_consultado))):
        nivel = NivelPrecisao.NUMERO_EXATO
    elif (diferenca is not None and diferenca <= DIFERENCA_NUMERO_MAXIMA
          and similaridade >= SIMILARIDADE_NUMERO):
        nivel = NivelPrecisao.NUMERO_APROXIMADO
    else:
        # Numeração distante ou logradouro mal casado não sustentam resposta no
        # nível do imóvel: a coordenada passa a valer como referência de via.
        nivel = NivelPrecisao.LOGRADOURO

    texto = linha.logradouro + (f', {linha.numero}' if linha.numero else '')
    lat, lon = float(linha.latitude), float(linha.longitude)

    return EnderecoResposta(
        endereco_encontrado=texto,
        codigo_municipio=getattr(linha, 'codigo_municipio', None),
        logradouro=linha.logradouro,
        numero=linha.numero,
        bairro=linha.bairro,
        cep=linha.cep,
        municipio=linha.municipio,
        uf=linha.uf,
        fonte=linha.fonte,
        versao_fonte=getattr(linha, 'versao_fonte', None),
        versao_dados=identificar_versao_dados(
            getattr(linha, 'fonte', None), getattr(linha, 'codigo_municipio', None),
            getattr(linha, 'versao_fonte', None), getattr(linha, 'arquivo_sha256', None),
            getattr(linha, 'qualidade_sha256', None),
            getattr(linha, 'processamento_sha256', None)),
        latitude=lat,
        longitude=lon,
        plus_code=plus_code(lat, lon),
        nivel_precisao=nivel,
        similaridade_logradouro=round(similaridade, 4) if similaridade is not None else None,
        diferenca_numero=diferenca if nivel is NivelPrecisao.NUMERO_APROXIMADO else None,
        qualidade=avaliar_qualidade(linha, nivel, similaridade, diferenca, tipo_consulta),
    )


CONSULTA_GEOCODE = text("""
    WITH ruas AS (
        SELECT lb.codigo_municipio, lb.municipio, lb.uf, lb.logradouro,
               similarity(lb.logradouro, :termo) AS sim
        FROM logradouro_busca lb
        WHERE lb.logradouro % :termo
          AND (:codigo_municipio IS NULL OR lb.codigo_municipio = :codigo_municipio)
          AND (:municipio IS NULL OR lb.municipio ILIKE :municipio)
          AND (:uf IS NULL OR lb.uf = :uf)
        ORDER BY sim DESC, lb.n_enderecos DESC, lb.codigo_municipio, lb.logradouro
        LIMIT :vias
    )
    SELECT e.id_endereco, e.logradouro, e.numero, e.numero_norm, e.bairro,
           e.bairro_norm, e.cep, e.codigo_municipio, e.municipio, e.uf,
           e.latitude, e.longitude,
           e.lci, e.mci, e.cdi, e.gci, e.n_unidades, e.dispersao_m,
           r.sim, f.nome AS fonte, e.versao_fonte,
           cr.arquivo_sha256, cr.qualidade_sha256, cr.processamento_sha256
    FROM ruas r
    JOIN endereco e ON e.logradouro = r.logradouro
                   AND e.codigo_municipio IS NOT DISTINCT FROM r.codigo_municipio
                   AND e.municipio IS NOT DISTINCT FROM r.municipio
                   AND e.uf IS NOT DISTINCT FROM r.uf
    JOIN fonte f ON f.id_fonte = e.id_fonte
    LEFT JOIN carga_repositorio cr ON cr.id_fonte = e.id_fonte
        AND cr.codigo_municipio = e.codigo_municipio
        AND cr.versao_fonte = e.versao_fonte
    WHERE (:codigo_municipio IS NULL OR e.codigo_municipio = :codigo_municipio)
      AND (:municipio IS NULL OR e.municipio ILIKE :municipio)
      AND (:uf IS NULL OR e.uf = :uf)
    ORDER BY
        r.sim DESC,
        CASE WHEN e.numero = :numero_completo THEN 0 ELSE 1 END,
        CASE WHEN :numero IS NULL THEN 0
             WHEN e.numero_norm IS NULL THEN 1000000
             ELSE abs(e.numero_norm - :numero) END,
        CASE WHEN :pistas IS NULL THEN 0
             WHEN e.bairro_norm = ANY(CAST(:pistas AS text[])) THEN 0 ELSE 1 END,
        e.n_unidades DESC, e.codigo_municipio, e.id_endereco
    LIMIT :limite
""")


def geocodificar(pedido: GeocodeRequest, db: Session, request: Request) -> GeocodeResultado:
    tratada = enriquecedor.tratar(pedido.endereco)
    termo, numero_texto, pistas = tratada.logradouro, tratada.numero, list(tratada.pistas)
    if not termo:
        raise HTTPException(status_code=400, detail='Consulta vazia após a normalização.')

    digitos = re.match(r'^\d+', numero_texto or '')
    numero = int(digitos.group()) if digitos else None
    if pedido.bairro:
        pistas = [normalize_logradouro(pedido.bairro)] + pistas

    db.execute(text('SET LOCAL pg_trgm.similarity_threshold = :limiar'),
               {'limiar': LIMIAR_SIMILARIDADE})
    linhas = db.execute(CONSULTA_GEOCODE, {
        'termo': termo,
        'numero': numero,
        'numero_completo': numero_texto,
        'limite': pedido.limite,
        # Número de nomes de via considerados. Mais de um permite que um erro de
        # digitação não descarte a via correta; muitos deixariam vias irrelevantes
        # disputarem a resposta pela proximidade do número.
        'vias': 5,
        'municipio': pedido.municipio,
        'uf': pedido.uf.upper() if pedido.uf else None,
        'codigo_municipio': pedido.codigo_municipio,
        'pistas': pistas or None,
    }).fetchall()

    if not linhas:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum endereço compatível com '{termo}' no recorte consultado.")

    # Abaixo do piso calibrado, responder é pior que não responder: na amostra do
    # NB14 essas consultas devolviam pontos a quilômetros do endereço pedido.
    linhas = [l for l in linhas if float(l.sim) >= SIMILARIDADE_MINIMA]
    if not linhas:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum logradouro suficientemente parecido com '{termo}' "
                   f"(similaridade mínima de {SIMILARIDADE_MINIMA:.2f}).")

    candidatos = [montar_resposta(linha, numero, numero_completo=numero_texto) for linha in linhas]
    request.state.resultados = len(candidatos)
    return GeocodeResultado(
        consulta=pedido.endereco,
        logradouro_normalizado=termo,
        numero_consultado=numero_texto,
        total=len(candidatos),
        candidatos=candidatos,
    )


@app.post('/geocode', response_model=GeocodeResultado, tags=['geocodificação'])
def geocode(pedido: GeocodeRequest, request: Request, db: Session = Depends(get_db)):
    """Geocodifica um endereço e devolve os candidatos com nível de precisão e qualidade."""
    return geocodificar(pedido, db, request)


@app.get('/geocode', response_model=GeocodeResultado, tags=['geocodificação'])
def geocode_get(request: Request,
                endereco: str = Query(..., min_length=2, max_length=300),
                municipio: Optional[str] = None,
                uf: Optional[str] = None,
                bairro: Optional[str] = None,
                codigo_municipio: Optional[str] = None,
                limite: int = Query(5, ge=1, le=20),
                db: Session = Depends(get_db)):
    """Mesma operação do POST, em forma de consulta por URL."""
    pedido = GeocodeRequest(endereco=endereco, municipio=municipio, uf=uf, bairro=bairro,
                            codigo_municipio=codigo_municipio, limite=limite)
    return geocodificar(pedido, db, request)


CONSULTA_REVERSA = text("""
    SELECT e.logradouro, e.numero, e.numero_norm, e.bairro, e.bairro_norm, e.cep,
           e.codigo_municipio, e.municipio, e.uf,
           e.latitude, e.longitude, e.lci, e.mci, e.cdi, e.gci, e.n_unidades,
           e.dispersao_m, f.nome AS fonte, e.versao_fonte,
           cr.arquivo_sha256, cr.qualidade_sha256, cr.processamento_sha256,
           NULL AS sim,
           ST_Distance(e.geom::geography,
                       ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
    FROM endereco e
    JOIN fonte f ON f.id_fonte = e.id_fonte
    LEFT JOIN carga_repositorio cr ON cr.id_fonte = e.id_fonte
        AND cr.codigo_municipio = e.codigo_municipio
        AND cr.versao_fonte = e.versao_fonte
    WHERE ST_DWithin(e.geom::geography,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :raio)
    ORDER BY dist_m, e.id_endereco
    LIMIT 1
""")


@app.post('/reverse', response_model=ReverseResposta, tags=['geocodificação'])
def reverse(pedido: ReverseRequest, request: Request, db: Session = Depends(get_db)):
    """Devolve o endereço mais próximo de uma coordenada, dentro do raio informado."""
    linha = db.execute(CONSULTA_REVERSA, {
        'lat': pedido.latitude, 'lon': pedido.longitude, 'raio': pedido.raio_m,
    }).fetchone()

    if not linha:
        raise HTTPException(
            status_code=404,
            detail=f'Nenhum endereço a até {pedido.raio_m:.0f} m da coordenada consultada.')

    base = montar_resposta(linha, None, tipo_consulta='reverse')
    request.state.resultados = 1
    distancia = float(linha.dist_m)
    qualidade = base.qualidade
    qualidade.motivo = (f'o endereço candidato está a {distancia:.0f} m da coordenada '
                        f'consultada, sem comprovação de identidade; {qualidade.motivo}')
    return ReverseResposta(**{**base.model_dump(), 'qualidade': qualidade,
                              'distancia_m': round(distancia, 2)})


@app.get('/cobertura', response_model=list[Cobertura], tags=['repositório'])
def cobertura(db: Session = Depends(get_db)):
    """O que está carregado no repositório, por município e fonte.

    Responde à pergunta que todo consumidor precisa fazer antes de usar o
    serviço: este repositório cobre o território que me interessa.
    """
    linhas = db.execute(text("""
        SELECT e.codigo_municipio, e.municipio, e.uf, f.nome AS fonte,
               count(*) AS enderecos, COALESCE(sum(e.n_unidades), 0) AS unidades
        FROM endereco e
        JOIN fonte f ON f.id_fonte = e.id_fonte
        GROUP BY 1, 2, 3, 4
        ORDER BY enderecos DESC
    """)).fetchall()
    return [Cobertura(codigo_municipio=l.codigo_municipio, municipio=l.municipio, uf=l.uf,
                      fonte=l.fonte, enderecos=l.enderecos, unidades=int(l.unidades))
            for l in linhas]


@app.get('/health', response_model=Saude, tags=['operação'])
def health(db: Session = Depends(get_db)):
    """Verificação de saúde: responde apenas se o banco estiver acessível."""
    try:
        linha = db.execute(text(
            'SELECT count(*) AS n, count(DISTINCT codigo_municipio) AS m FROM endereco'
        )).fetchone()
    except Exception:
        logger.exception('Falha na consulta de saúde ao banco')
        raise HTTPException(status_code=503, detail='Banco indisponível.')
    return Saude(status='ok', banco='ok', enderecos=linha.n, municipios=linha.m, versao=VERSAO)


@app.get('/usage', response_model=UsoResultado, tags=['operação'])
def usage(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """Contabilização de uso apurada no banco, por rota e por cliente."""
    por_rota = db.execute(text("""
        SELECT rota, count(*) AS requisicoes, round(avg(latencia_ms)::numeric, 1) AS latencia,
               count(*) FILTER (WHERE status >= 400) AS erros
        FROM uso_api
        WHERE momento >= now() - make_interval(days => :dias)
        GROUP BY rota ORDER BY requisicoes DESC
    """), {'dias': dias}).fetchall()

    por_cliente = db.execute(text("""
        SELECT cliente, count(*) AS requisicoes
        FROM uso_api
        WHERE momento >= now() - make_interval(days => :dias)
        GROUP BY cliente ORDER BY requisicoes DESC
    """), {'dias': dias}).fetchall()

    return UsoResultado(
        desde=f'últimos {dias} dias',
        total=sum(l.requisicoes for l in por_rota),
        por_rota=[UsoPorRota(rota=l.rota, requisicoes=l.requisicoes,
                             latencia_media_ms=float(l.latencia) if l.latencia is not None else None,
                             erros=l.erros) for l in por_rota],
        por_cliente={l.cliente: l.requisicoes for l in por_cliente},
        telemetria_descartada_processo=contabilizador.descartados,
        telemetria_pendente_processo=contabilizador.pendentes,
        limite_por_minuto_processo=limitador.limite,
    )


@app.get('/', tags=['operação'])
def raiz():
    return {
        'servico': 'Repositório de endereços de referência',
        'versao': VERSAO,
        'documentacao': '/docs',
        'rotas': ['/geocode', '/reverse', '/cobertura', '/health', '/usage'],
    }
