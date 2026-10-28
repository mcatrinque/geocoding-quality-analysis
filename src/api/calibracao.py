"""Distribuições de erro observadas para uma política e um conjunto de dados específicos.

A tabela legada de BH foi produzida durante o ajuste da política de resposta.
Sem identificação de teste independente, dados e política, ela não habilita
estatísticas na API. Ausência ou defeito da evidência deixa a classe declarada.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Optional

from .schemas import Calibracao, ClasseConfianca, NivelPrecisao, StatusCalibracao

logger = logging.getLogger(__name__)
RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ / 'dados_replicacao' / 'calibracao_bh.csv'
NAO_CALIBRADA = Calibracao(status=StatusCalibracao.DECLARADA)
MINIMO_AMOSTRA = 100
BASES = {'nivel+confianca', 'nivel', 'global'}
COLUNAS = {'codigo_municipio', 'nivel', 'confianca', 'base', 'n',
           'erro_mediano_m', 'erro_ce90_m', 'acima_30_pct', 'acima_100_pct',
           'versao_dados', 'versao_politica', 'tipo_consulta', 'amostra',
           'fonte_referencia'}
HASH = re.compile(r'[0-9a-f]{64}')


def identificar_versao_dados(fonte: Optional[str], codigo_municipio: Optional[str],
                             versao_fonte: Optional[str], arquivo_sha256: Optional[str],
                             qualidade_sha256: Optional[str],
                             processamento_sha256: Optional[str]) -> Optional[str]:
    """Identifica o conjunto carregado a partir do manifesto persistido no banco."""
    codigo = (codigo_municipio or '').strip()
    arquivo = (arquivo_sha256 or '').strip().lower()
    qualidade = (qualidade_sha256 or '').strip().lower() or None
    processamento = (processamento_sha256 or '').strip().lower()
    if (not fonte or not versao_fonte or len(codigo) != 7 or not codigo.isdigit()
            or not HASH.fullmatch(arquivo) or not HASH.fullmatch(processamento)
            or (qualidade is not None and not HASH.fullmatch(qualidade))):
        return None
    conteudo = dict(fonte=fonte, codigo_municipio=codigo,
                    versao_fonte=versao_fonte, arquivo_sha256=arquivo,
                    qualidade_sha256=qualidade, processamento_sha256=processamento)
    return hashlib.sha256(json.dumps(conteudo, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


class AmostraInsuficiente(ValueError):
    pass


def _numero(valor: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError('número não finito')
    return numero


def _validar(linha: dict) -> dict:
    if not COLUNAS.issubset(linha):
        raise ValueError('colunas de procedência ou métricas ausentes')
    municipio = (linha['codigo_municipio'] or '').strip()
    nivel = (linha['nivel'] or '').strip()
    confianca = (linha['confianca'] or '').strip()
    base = (linha['base'] or '').strip()
    if not municipio.isdigit() or len(municipio) != 7 or base not in BASES:
        raise ValueError('município ou granularidade inválidos')
    if base == 'global' and (nivel or confianca):
        raise ValueError('chave global inválida')
    if base == 'nivel' and (nivel not in NivelPrecisao._value2member_map_ or confianca):
        raise ValueError('chave de nível inválida')
    if base == 'nivel+confianca' and (nivel not in NivelPrecisao._value2member_map_
                                      or confianca not in ClasseConfianca._value2member_map_):
        raise ValueError('chave de par inválida')
    for campo in ('versao_dados', 'versao_politica', 'fonte_referencia'):
        if not (linha[campo] or '').strip():
            raise ValueError(f'{campo} ausente')
    if not HASH.fullmatch(linha['versao_dados']):
        raise ValueError('versão de dados inválida')
    if linha['tipo_consulta'] != 'geocode' or linha['amostra'] != 'teste_independente':
        raise ValueError('rota ou amostra não elegível')
    n = _numero(linha['n'])
    if not n.is_integer() or n < 0:
        raise ValueError('contagem inválida')
    if n < MINIMO_AMOSTRA:
        raise AmostraInsuficiente('contagem insuficiente')
    mediana = _numero(linha['erro_mediano_m'])
    ce90 = _numero(linha['erro_ce90_m'])
    taxa30 = _numero(linha['acima_30_pct'])
    taxa100 = _numero(linha['acima_100_pct'])
    if not (0 <= mediana <= ce90 and 0 <= taxa100 <= taxa30 <= 100):
        raise ValueError('quantis ou taxas fora de ordem')
    for limiar, taxa in ((30, taxa30), (100, taxa100)):
        if ce90 < limiar and taxa > 10.01:
            raise ValueError('taxa incompatível com CE90')
        if mediana < limiar and taxa > 50.01:
            raise ValueError('taxa incompatível com mediana')
        if mediana > limiar and taxa < 49.99:
            raise ValueError('taxa incompatível com mediana')
        if ce90 > limiar and taxa < 9.99:
            raise ValueError('taxa incompatível com CE90')
    return {**linha, 'codigo_municipio': municipio, 'nivel': nivel,
            'confianca': confianca, 'base': base, 'n': int(n),
            'erro_mediano_m': mediana, 'erro_ce90_m': ce90,
            'acima_30_pct': taxa30, 'acima_100_pct': taxa100}


class Calibrador:
    def __init__(self, linhas: Optional[list[dict]] = None):
        self._por_conjunto: dict[tuple[str, str], dict[tuple[str, str], dict]] = {}
        try:
            for original in linhas or []:
                try:
                    linha = _validar(original)
                except AmostraInsuficiente:
                    continue
                municipio = linha['codigo_municipio']
                chave = (linha['nivel'], linha['confianca'])
                tabela = self._por_conjunto.setdefault((municipio, linha['versao_dados']), {})
                if chave in tabela:
                    raise ValueError('célula duplicada')
                tabela[chave] = linha
            for tabela in self._por_conjunto.values():
                global_linha = tabela.get(('', ''))
                if global_linha is None:
                    raise ValueError('total global ausente')
                metadados = ('versao_dados', 'versao_politica', 'tipo_consulta',
                             'amostra', 'fonte_referencia')
                for (nivel, confianca), linha in tabela.items():
                    if any(linha[campo] != global_linha[campo] for campo in metadados):
                        raise ValueError('procedência inconsistente')
                    if linha['n'] > global_linha['n']:
                        raise ValueError('contagem maior que o total')
                    nivel_linha = tabela.get((nivel, '')) if confianca else None
                    if nivel_linha and linha['n'] > nivel_linha['n']:
                        raise ValueError('contagem do par maior que a do nível')
        except (TypeError, ValueError, KeyError) as erro:
            logger.warning('Tabela de calibração inválida: %s', erro)
            self._por_conjunto.clear()

    @property
    def municipios_calibrados(self) -> list[str]:
        return sorted({municipio for municipio, _ in self._por_conjunto})

    def consultar(self, codigo_municipio: Optional[str], nivel: Optional[NivelPrecisao],
                  confianca: Optional[ClasseConfianca], *,
                  versao_dados: Optional[str] = None,
                  versao_politica: Optional[str] = None,
                  tipo_consulta: str = 'geocode') -> Calibracao:
        tabela = self._por_conjunto.get(((codigo_municipio or '').strip(), versao_dados or ''))
        if not tabela or not versao_dados or not versao_politica or tipo_consulta != 'geocode':
            return NAO_CALIBRADA
        nivel_txt = nivel.value if nivel is not None else ''
        conf_txt = confianca.value if confianca is not None else ''
        for chave in ((nivel_txt, conf_txt), (nivel_txt, ''), ('', '')):
            linha = tabela.get(chave)
            if linha is not None:
                break
        else:
            return NAO_CALIBRADA
        if linha['versao_politica'] != versao_politica:
            return NAO_CALIBRADA
        global_linha = tabela.get(('', ''))
        n_total = global_linha['n'] if global_linha else None
        referencia = linha['fonte_referencia']
        if n_total:
            referencia += f', {n_total:,} endereços medidos'.replace(',', '.')
        return Calibracao(
            status=StatusCalibracao.CALIBRADA, referencia=referencia,
            base=linha['base'], n_amostra=linha['n'],
            erro_mediano_m=linha['erro_mediano_m'], erro_ce90_m=linha['erro_ce90_m'],
            acima_de_30_m_pct=linha['acima_30_pct'],
            acima_de_100_m_pct=linha['acima_100_pct'],
            versao_dados=versao_dados, versao_politica=versao_politica,
            tipo_consulta=tipo_consulta, amostra='teste_independente')


def carregar(caminho: Optional[Path] = None) -> Calibrador:
    caminho = Path(caminho or os.environ.get('CALIBRACAO_CSV') or CAMINHO_PADRAO)
    try:
        with caminho.open(encoding='utf-8', newline='') as arquivo:
            linhas = list(csv.DictReader(arquivo))
        return Calibrador(linhas)
    except (OSError, UnicodeError, csv.Error) as erro:
        logger.warning('Tabela de calibração indisponível: %s', erro)
        return Calibrador()


_calibrador: Optional[Calibrador] = None


def obter_calibrador() -> Calibrador:
    global _calibrador
    if _calibrador is None:
        _calibrador = carregar()
    return _calibrador
