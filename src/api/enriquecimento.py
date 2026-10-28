"""Tratamento do endereço de entrada, com ponto de extensão declarado.

A consulta que chega à API é texto livre e carrega os problemas do texto livre:
abreviações, erros de digitação, ordem trocada dos componentes, referências
informais de localização. O repositório trata isso hoje por regras
determinísticas, isto é, forma canônica e separação em componentes.

Este módulo isola esse tratamento atrás de uma interface para que a substituição
por métodos de inteligência artificial, prevista como trabalho futuro, seja uma
troca de implementação e não uma alteração da rota. O ponto de extensão fica
declarado no código, e não apenas no texto da dissertação: o
`EnriquecedorPorModeloDeLinguagem` existe, documenta o contrato que precisa
cumprir e falha de forma explícita enquanto não houver implementação, em vez de
silenciosamente cair no comportamento padrão.

Seleção por ambiente, com `ENRIQUECEDOR=canonico` (padrão) ou `ENRIQUECEDOR=llm`.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from ..normalize import partes_endereco


@dataclass
class ConsultaTratada:
    """Resultado do tratamento do endereço de entrada."""

    logradouro: str
    numero: Optional[str] = None
    pistas: List[str] = field(default_factory=list)
    tratamento: str = 'canonico'
    observacoes: List[str] = field(default_factory=list)


class Enriquecedor(Protocol):
    """Contrato de qualquer tratamento de endereço de entrada."""

    nome: str

    def tratar(self, consulta: str) -> ConsultaTratada:
        ...


class EnriquecedorCanonico:
    """Tratamento determinístico, em produção.

    Aplica a forma canônica do repositório, expande abreviações de tipo de
    logradouro, remove acentuação e separa número e pistas territoriais.
    """

    nome = 'canonico'

    def tratar(self, consulta: str) -> ConsultaTratada:
        logradouro, numero, pistas = partes_endereco(consulta)
        return ConsultaTratada(logradouro=logradouro, numero=numero, pistas=pistas,
                               tratamento=self.nome)


class EnriquecedorPorModeloDeLinguagem:
    """Ponto de extensão para o tratamento assistido por modelo de linguagem.

    Não implementado. O contrato que uma implementação precisa cumprir:

    1. Devolver `ConsultaTratada` com o logradouro já em forma canônica do
       repositório, de modo que a busca por trigrama continue comparando o
       mesmo alfabeto.
    2. Ser determinístico o suficiente para que a mesma consulta produza a mesma
       resposta, requisito de reprodutibilidade da avaliação de qualidade.
    3. Registrar em `observacoes` o que foi inferido e não estava no texto
       original, para que a indicação de qualidade da resposta possa ser
       rebaixada quando a interpretação depender de inferência.
    4. Degradar para `EnriquecedorCanonico` quando o serviço externo falhar ou
       exceder o tempo limite, jamais bloqueando a consulta.

    O terceiro item é o que liga esta extensão à contribuição da dissertação:
    um endereço reconstruído por inferência não pode ser apresentado com a mesma
    confiança de um endereço que casou literalmente.
    """

    nome = 'llm'

    def tratar(self, consulta: str) -> ConsultaTratada:
        raise NotImplementedError(
            'O tratamento por modelo de linguagem é um ponto de extensão previsto na '
            'arquitetura e ainda não implementado. Use ENRIQUECEDOR=canonico.')


_REGISTRO: Dict[str, type] = {
    EnriquecedorCanonico.nome: EnriquecedorCanonico,
    EnriquecedorPorModeloDeLinguagem.nome: EnriquecedorPorModeloDeLinguagem,
}


def obter_enriquecedor(nome: Optional[str] = None) -> Enriquecedor:
    escolhido = (nome or os.environ.get('ENRIQUECEDOR', 'canonico')).strip().lower()
    if escolhido not in _REGISTRO:
        raise ValueError(
            f"Enriquecedor '{escolhido}' desconhecido. "
            f"Disponíveis: {', '.join(sorted(_REGISTRO))}.")
    return _REGISTRO[escolhido]()
