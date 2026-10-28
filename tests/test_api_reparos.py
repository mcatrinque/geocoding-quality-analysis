"""Regressões dos contratos de evidência e de busca da API."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.calibracao import Calibrador, identificar_versao_dados
from src.api.schemas import ClasseConfianca, NivelPrecisao, StatusCalibracao

BH = '3106200'
VERSAO_TESTE = 'a' * 64
METADADOS = dict(versao_dados=VERSAO_TESTE, versao_politica='politica-teste',
                 tipo_consulta='geocode', amostra='teste_independente',
                 fonte_referencia='BHMap')
LINHAS = [
    dict(codigo_municipio=BH, nivel='numero_exato', confianca='alta',
         base='nivel+confianca', n='16217', erro_mediano_m='8.2',
         erro_ce90_m='20.98', acima_30_pct='5.77', acima_100_pct='1.83',
         **METADADOS),
    dict(codigo_municipio=BH, nivel='numero_exato', confianca='',
         base='nivel', n='16391', erro_mediano_m='8.23',
         erro_ce90_m='21.1', acima_30_pct='5.8', acima_100_pct='1.81',
         **METADADOS),
    dict(codigo_municipio=BH, nivel='', confianca='',
         base='global', n='19924', erro_mediano_m='9.38',
         erro_ce90_m='57.94', acima_30_pct='14.76', acima_100_pct='7.99',
         **METADADOS),
]


def consultar(calibrador, municipio, nivel, confianca):
    return calibrador.consultar(municipio, nivel, confianca,
                                versao_dados=VERSAO_TESTE,
                                versao_politica='politica-teste')


@pytest.mark.parametrize('campo,valor', [
    ('n', '100.5'), ('n', 'inf'),
    ('erro_mediano_m', '-1'), ('erro_mediano_m', 'nan'),
    ('erro_ce90_m', '2'), ('erro_ce90_m', 'inf'),
    ('acima_30_pct', '120'), ('acima_30_pct', '40'),
    ('acima_100_pct', '20'), ('acima_100_pct', 'texto'),
])
def test_tabela_defeituosa_nao_publica_estimativas(campo, valor):
    linhas = deepcopy(LINHAS)
    linhas[0][campo] = valor
    calibrador = Calibrador(linhas)
    assert consultar(calibrador, BH, NivelPrecisao.NUMERO_EXATO,
                     ClasseConfianca.ALTA).status is StatusCalibracao.DECLARADA


def test_celula_pequena_recua_para_o_nivel():
    linhas = deepcopy(LINHAS)
    linhas[0]['n'] = '99'
    calibrador = Calibrador(linhas)
    resultado = consultar(calibrador, BH, NivelPrecisao.NUMERO_EXATO,
                          ClasseConfianca.ALTA)
    assert resultado.status is StatusCalibracao.CALIBRADA
    assert resultado.base == 'nivel'
    assert resultado.n_amostra == 16391


def test_calibracao_exige_versoes_e_teste_independente():
    calibrador = Calibrador(deepcopy(LINHAS))
    assert calibrador.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA,
                                versao_dados='outra',
                                versao_politica='politica-teste').status is StatusCalibracao.DECLARADA
    assert calibrador.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA,
                                versao_dados=VERSAO_TESTE,
                                versao_politica='outra').status is StatusCalibracao.DECLARADA
    assert calibrador.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA,
                                versao_dados=VERSAO_TESTE,
                                versao_politica='politica-teste',
                                tipo_consulta='reverse').status is StatusCalibracao.DECLARADA
    linhas = deepcopy(LINHAS)
    linhas[0]['amostra'] = 'desenvolvimento'
    assert Calibrador(linhas).municipios_calibrados == []


def test_contagem_e_procedencia_precisam_ser_coerentes():
    linhas = deepcopy(LINHAS)
    linhas[0]['n'] = '30000'
    assert Calibrador(linhas).municipios_calibrados == []
    linhas = deepcopy(LINHAS)
    linhas[1]['versao_dados'] = 'outra'
    assert Calibrador(linhas).municipios_calibrados == []


def _linha_reversa():
    return SimpleNamespace(
        logradouro='RUA TESTE', numero='10', numero_norm=10,
        bairro=None, cep=None, municipio='Belo Horizonte', uf='MG', fonte='CNEFE',
        codigo_municipio=BH, latitude=-19.9, longitude=-43.9,
        sim=None, dist_m=2.0, lci=1.0, mci=None, cdi=1, gci=None,
        n_unidades=1, dispersao_m=0.0)


def test_reversa_proxima_nao_afirma_numero_exato(monkeypatch):
    from src.api import main

    class DB:
        def execute(self, comando, parametros):
            return SimpleNamespace(fetchone=lambda: _linha_reversa())

    pedido = main.ReverseRequest(latitude=-19.9, longitude=-43.9)
    request = SimpleNamespace(state=SimpleNamespace())
    resposta = main.reverse(pedido, request, DB())
    assert resposta.nivel_precisao is NivelPrecisao.PROXIMIDADE
    assert resposta.similaridade_logradouro is None
    assert resposta.qualidade.calibracao.status is StatusCalibracao.DECLARADA
    assert resposta.distancia_m == 2.0
    assert 'sem comprovação de identidade' in resposta.qualidade.motivo


def test_cdi_nao_comprova_identidade_de_edificio():
    from src.api import main

    linha = _linha_reversa()
    linha.cdi = 42
    qualidade = main.avaliar_qualidade(linha, NivelPrecisao.PROXIMIDADE,
                                      None, None, tipo_consulta='reverse')
    assert '42 registros da fonte compartilham esta coordenada' in qualidade.motivo
    assert 'não identifica unidades físicas' in qualidade.motivo
    assert 'identifica o edifício' not in qualidade.motivo


def test_health_nao_expoe_erro_do_banco():
    from src.api import main

    class DB:
        def execute(self, comando):
            raise RuntimeError('senha e host internos')

    with pytest.raises(HTTPException) as erro:
        main.health(DB())
    assert erro.value.status_code == 503
    assert 'senha' not in erro.value.detail


def test_sufixo_diferente_nao_e_numero_exato():
    from src.api import main

    linha = _linha_reversa()
    linha.sim = 1.0
    linha.numero = '10A'
    assert main.montar_resposta(linha, 10, numero_completo='10').nivel_precisao is NivelPrecisao.NUMERO_APROXIMADO
    assert main.montar_resposta(linha, 10, numero_completo='10A').nivel_precisao is NivelPrecisao.NUMERO_EXATO


def test_variavel_ambiente_nao_certifica_banco_sem_proveniencia(monkeypatch):
    from src.api import main

    monkeypatch.setenv('VERSAO_DADOS_REPOSITORIO', 'dados-teste')
    monkeypatch.setattr(main, 'VERSAO_POLITICA', 'politica-teste')
    monkeypatch.setattr(main, 'obter_calibrador', lambda: Calibrador(deepcopy(LINHAS)))
    linha = _linha_reversa()
    resultado = main.avaliar_qualidade(linha, NivelPrecisao.NUMERO_EXATO, 1.0, 0)
    assert resultado.calibracao.status is StatusCalibracao.DECLARADA


def test_manifesto_real_identifica_fonte_versao_e_processamento(monkeypatch):
    from src.api import main

    linha = _linha_reversa()
    linha.fonte = 'CNEFE_2022'
    linha.versao_fonte = '2022'
    linha.arquivo_sha256 = '1' * 64
    linha.qualidade_sha256 = '2' * 64
    linha.processamento_sha256 = '3' * 64
    identidade = identificar_versao_dados(
        linha.fonte, linha.codigo_municipio, linha.versao_fonte,
        linha.arquivo_sha256, linha.qualidade_sha256, linha.processamento_sha256)
    assert identidade is not None
    linhas = deepcopy(LINHAS)
    for item in linhas:
        item['versao_dados'] = identidade
    monkeypatch.setattr(main, 'VERSAO_POLITICA', 'politica-teste')
    monkeypatch.setattr(main, 'obter_calibrador', lambda: Calibrador(linhas))
    assert main.avaliar_qualidade(linha, NivelPrecisao.NUMERO_EXATO, 1.0,
                                  0).calibracao.status is StatusCalibracao.CALIBRADA
    linha.processamento_sha256 = '4' * 64
    assert main.avaliar_qualidade(linha, NivelPrecisao.NUMERO_EXATO, 1.0,
                                  0).calibracao.status is StatusCalibracao.DECLARADA
    linha.processamento_sha256 = '3' * 64
    linha.fonte = 'outra_fonte'
    assert main.avaliar_qualidade(linha, NivelPrecisao.NUMERO_EXATO, 1.0,
                                  0).calibracao.status is StatusCalibracao.DECLARADA


def test_manifesto_incompleto_nao_gera_versao():
    assert identificar_versao_dados('CNEFE', BH, '2022', '1' * 64,
                                    None, None) is None
    assert identificar_versao_dados('CNEFE', BH, '2022', 'invalido',
                                    None, '3' * 64) is None


def test_duas_versoes_do_mesmo_municipio_nao_se_sobrepoem():
    linhas = deepcopy(LINHAS)
    novas = deepcopy(LINHAS)
    for item in novas:
        item['versao_dados'] = 'b' * 64
        item['erro_mediano_m'] = '7.0'
    calibrador = Calibrador(linhas + novas)
    antiga = calibrador.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA,
                                  versao_dados=VERSAO_TESTE,
                                  versao_politica='politica-teste')
    nova = calibrador.consultar(BH, NivelPrecisao.NUMERO_EXATO, ClasseConfianca.ALTA,
                                versao_dados='b' * 64,
                                versao_politica='politica-teste')
    assert antiga.erro_mediano_m == 8.2
    assert nova.erro_mediano_m == 7.0


def test_sql_mantem_municipio_e_ordena_reversa_em_metros():
    from src.api import main

    geocode = str(main.CONSULTA_GEOCODE)
    reversa = str(main.CONSULTA_REVERSA)
    assert 'e.codigo_municipio IS NOT DISTINCT FROM r.codigo_municipio' in geocode
    assert 'cr.id_fonte = e.id_fonte' in geocode
    assert 'cr.processamento_sha256' in geocode
    assert 'e.id_endereco' in geocode.split('ORDER BY')[-1]
    assert 'ORDER BY dist_m, e.id_endereco' in reversa
    assert 'e.geom <->' not in reversa


def test_telemetria_declara_perdas_e_limite_por_processo():
    from src.api.metering import Contabilizador, LimitadorDeTaxa, Registro

    contador = Contabilizador(engine=None, tamanho_fila=1)
    registro = Registro(rota='/geocode', metodo='GET', status=200,
                        latencia_ms=1, cliente='teste')
    contador.registrar(registro)
    contador.registrar(registro)
    assert contador.pendentes == 1
    assert contador.descartados == 1
    processo_a = LimitadorDeTaxa(1)
    processo_b = LimitadorDeTaxa(1)
    assert processo_a.permitido('teste', 1)
    assert not processo_a.permitido('teste', 1)
    assert processo_b.permitido('teste', 1)
