"""Testes do ponto de extensão do tratamento do endereço de entrada.

O tratamento por métodos de inteligência artificial é trabalho futuro declarado.
O que se garante aqui é que o ponto de injeção existe, que o comportamento padrão
é o determinístico e que uma implementação ausente falha de forma explícita, em
vez de degradar silenciosamente para outro comportamento.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api.enriquecimento import (ConsultaTratada, EnriquecedorCanonico,
                                    EnriquecedorPorModeloDeLinguagem, obter_enriquecedor)


def test_padrao_e_o_tratamento_canonico():
    assert obter_enriquecedor().nome == EnriquecedorCanonico.nome


def test_tratamento_canonico_decompoe_o_endereco():
    tratada = obter_enriquecedor('canonico').tratar('Rua da Bahia, 1000, Centro, Belo Horizonte')
    assert isinstance(tratada, ConsultaTratada)
    assert tratada.logradouro == 'RUA DA BAHIA'
    assert tratada.numero == '1000'
    assert tratada.pistas == ['CENTRO', 'BELO HORIZONTE']
    assert tratada.observacoes == []


def test_ponto_de_extensao_falha_de_forma_explicita():
    with pytest.raises(NotImplementedError) as erro:
        EnriquecedorPorModeloDeLinguagem().tratar('Avenida Afonso Pena, 1212')
    assert 'ponto de extens' in str(erro.value)


def test_enriquecedor_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        obter_enriquecedor('inexistente')
