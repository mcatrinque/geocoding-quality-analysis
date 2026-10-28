"""Contratos espaciais do enriquecimento contextual em EPSG:31983."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, box

from scripts import enrich_master_metrics as enriquecimento


CRS = 'EPSG:31983'


def _pontos(coordenadas, indices=None):
    return gpd.GeoDataFrame(
        geometry=[Point(x, y) for x, y in coordenadas],
        index=indices,
        crs=CRS,
    )


def _poligonos(geometrias, **atributos):
    return gpd.GeoDataFrame(atributos, geometry=geometrias, crs=CRS)


def test_sjoin_preserva_ordem_cardinalidade_e_consenso_independente_da_camada():
    pontos = _pontos([(5, 5), (25, 5), (50, 5)], indices=[20, 10, 30])
    camada = _poligonos(
        [box(0, 0, 10, 10), box(0, 0, 15, 15), box(20, 0, 30, 10)],
        CONSENSO=['residencial', 'residencial', 'comercial'],
        DIVERGE=['A', 'B', 'C'],
    )

    primeiro = enriquecimento._sjoin_dedup(pontos, camada)
    invertido = enriquecimento._sjoin_dedup(pontos, camada.iloc[::-1])

    for resultado in [primeiro, invertido]:
        assert len(resultado) == len(pontos)
        assert resultado.index.tolist() == [20, 10, 30]
        assert resultado['_n_candidatos'].tolist() == [2, 1, 0]
        assert resultado.loc[20, 'CONSENSO'] == 'residencial'
        assert pd.isna(resultado.loc[20, 'DIVERGE'])
        assert resultado.loc[10, 'CONSENSO'] == 'comercial'
        assert resultado.loc[10, 'DIVERGE'] == 'C'
        assert pd.isna(resultado.loc[30, 'CONSENSO'])
        assert pd.isna(resultado.loc[30, 'DIVERGE'])
    pd.testing.assert_series_equal(primeiro['CONSENSO'], invertido['CONSENSO'])
    pd.testing.assert_series_equal(primeiro['DIVERGE'], invertido['DIVERGE'])


def test_fallback_vila_favela_usa_presenca_espacial_sem_rotulo(monkeypatch):
    pontos = _pontos([(5, 5), (20, 20)], indices=[4, 8])
    camada = _poligonos([box(0, 0, 10, 10)])
    pasta_ausente = Path(__file__).parent / '__camada_ausente__'
    monkeypatch.setattr(enriquecimento, 'PROC', pasta_ausente)
    monkeypatch.setattr(enriquecimento.config, 'VILAS_FAVELAS_SHP', pasta_ausente / 'vila.shp')
    monkeypatch.setattr(enriquecimento.gpd, 'read_file', lambda path: camada)

    resultado = enriquecimento.join_vila_favela_enriched(pontos.copy())

    assert resultado.index.tolist() == [4, 8]
    assert resultado['em_favela'].tolist() == [1, 0]


def test_flag_estabelecimento_usa_especies_e_nao_construcao():
    especies = [3, 4, 5, 6, 7, 8, 1]
    pontos = _pontos([(n, 0) for n in range(len(especies))])
    pontos['COD_ESPECIE'] = especies

    resultado = enriquecimento.add_internal_flags(pontos)

    assert resultado['FLAG_ESTABELECIMENTO'].tolist() == [1, 1, 1, 1, 0, 1, 0]


def test_riscos_sobrepostos_preservam_as_duas_ocorrencias(monkeypatch):
    pontos = _pontos([(5, 5), (12, 5), (30, 30)], indices=[2, 6, 9])
    riscos = _poligonos(
        [box(0, 0, 15, 10), box(0, 0, 10, 10)],
        TIPO_RISCO=['INUNDACAO', 'ESCORREGAMENTO'],
    )
    monkeypatch.setattr(enriquecimento, 'PROC', Path(__file__).parent / '__camada_ausente__')
    monkeypatch.setattr(enriquecimento.gpd, 'read_parquet', lambda path: riscos)

    resultado = enriquecimento.join_area_risco(pontos.copy())

    assert resultado.index.tolist() == [2, 6, 9]
    assert resultado['em_inundacao'].tolist() == [1, 1, 0]
    assert resultado['em_escorregamento'].tolist() == [1, 0, 0]
    assert resultado['em_risco'].tolist() == [1, 1, 0]


def test_atividade_usa_setor_declarado_com_sufixo_sem_alterar_original(monkeypatch):
    setor_com_evento = '123456789012345'
    setor_sem_evento = '123456789012346'
    setor_desconhecido = '123456789012347'
    pontos = _pontos([(5, 5), (6, 5), (25, 5), (45, 5), (55, 5)])
    declarados = [setor_com_evento + 'P', setor_com_evento + 'S',
                  setor_sem_evento + 'S', setor_desconhecido + 'P', 'invalido']
    pontos['COD_SETOR'] = declarados
    pontos['COD_ESPECIE'] = [1] * len(pontos)
    eventos = _pontos([(5, 5)])
    setores = _poligonos(
        [box(0, 0, 10, 10), box(20, 0, 30, 10)],
        COD_SETOR=[setor_com_evento, setor_sem_evento],
        AREA_KM2_SETOR=[2.0, 1.0],
    )
    pasta = Path(__file__).parent / '__camadas_sinteticas__'
    monkeypatch.setattr(enriquecimento, 'PROC', pasta)
    existe_original = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda path: path.name in {
        'atividade_economica.parquet', 'setor_censitario.parquet'} or existe_original(path))
    monkeypatch.setattr(enriquecimento.gpd, 'read_parquet',
                        lambda path: eventos if path.name == 'atividade_economica.parquet' else setores)

    resultado = enriquecimento.join_atividade_economica(pontos.copy())

    assert resultado['COD_SETOR'].tolist() == declarados
    densidade = resultado['DENS_ATIV_ECON_KM2']
    assert densidade.iloc[:3].tolist() == [0.5, 0.5, 0.0]
    assert pd.isna(densidade.iloc[3])
    assert pd.isna(densidade.iloc[4])


def test_empate_da_via_preserva_consenso_e_anula_discordancia(monkeypatch):
    pontos = _pontos([(5, 5), (20, 5)], indices=[21, 11])
    vias = gpd.GeoDataFrame({
        'VIA_CLASSIFICA': ['LOCAL', 'LOCAL'],
        'VIA_HIERARQUIA': [1, 1],
        'VIA_TIPO_LOG': ['RUA', 'AVENIDA'],
    }, geometry=[LineString([(0, 0), (0, 10)]),
                 LineString([(10, 0), (10, 10)])], crs=CRS)
    pasta = Path(__file__).parent / '__camadas_sinteticas__'
    monkeypatch.setattr(enriquecimento, 'PROC', pasta)
    existe_original = Path.exists
    monkeypatch.setattr(Path, 'exists',
                        lambda path: path.name == 'via_classifica.parquet' or existe_original(path))
    monkeypatch.setattr(enriquecimento.gpd, 'read_parquet', lambda path: vias)

    resultado = enriquecimento.join_via_classifica(pontos.copy())

    assert resultado.index.tolist() == [21, 11]
    assert resultado['VIA_CLASSIFICA'].tolist() == ['LOCAL', 'LOCAL']
    assert resultado['VIA_HIERARQUIA'].tolist() == [1, 1]
    assert pd.isna(resultado.loc[21, 'VIA_TIPO_LOG'])
    assert resultado.loc[11, 'VIA_TIPO_LOG'] == 'AVENIDA'
    assert resultado['DIST_VIA_CONTEXTO_M'].tolist() == [5.0, 10.0]
