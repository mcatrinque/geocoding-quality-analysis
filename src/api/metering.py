"""Contabilização de uso da API.

O registro vai para a tabela `uso_api`, e não para memória, porque um contador
em processo zera a cada reinício do container e não distingue clientes. A
gravação acontece numa fila com escrita em lote, de modo que a requisição não
espera o banco: se a fila encher, o registro é descartado em vez de atrasar a
resposta, já que medir uso nunca deve derrubar o serviço.
"""

import os
import queue
import threading
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text


@dataclass
class Registro:
    rota: str
    metodo: str
    status: int
    latencia_ms: int
    cliente: str
    resultados: Optional[int] = None


class Contabilizador:
    def __init__(self, engine, tamanho_fila: int = 10_000, lote: int = 50,
                 intervalo_s: float = 2.0):
        self._engine = engine
        self._fila: "queue.Queue[Optional[Registro]]" = queue.Queue(maxsize=tamanho_fila)
        self._lote = lote
        self._intervalo = intervalo_s
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._consumir, name='metering', daemon=True)
        self.descartados = 0

    @property
    def pendentes(self) -> int:
        return self._fila.qsize()

    def iniciar(self):
        if self._thread.is_alive():
            if self._parar.is_set():
                raise RuntimeError('Contabilizador ainda está encerrando')
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._consumir, name='metering', daemon=True)
        self._thread.start()

    def registrar(self, registro: Registro):
        try:
            self._fila.put_nowait(registro)
        except queue.Full:
            self.descartados += 1

    def encerrar(self, espera_s: float = 5.0):
        self._parar.set()
        try:
            self._fila.put_nowait(None)
        except queue.Full:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=espera_s)

    def _consumir(self):
        pendentes = []
        while not (self._parar.is_set() and self._fila.empty() and not pendentes):
            try:
                item = self._fila.get(timeout=self._intervalo)
                if item is not None:
                    pendentes.append(item)
            except queue.Empty:
                pass
            if pendentes and (len(pendentes) >= self._lote or self._fila.empty()):
                self._gravar(pendentes)
                pendentes = []

    def _gravar(self, registros):
        comando = text("""
            INSERT INTO uso_api (rota, metodo, status, latencia_ms, cliente, resultados)
            VALUES (:rota, :metodo, :status, :latencia_ms, :cliente, :resultados)
        """)
        try:
            with self._engine.begin() as conexao:
                conexao.execute(comando, [r.__dict__ for r in registros])
        except Exception:
            # Perder telemetria é aceitável; interromper o serviço por causa dela não é.
            self.descartados += len(registros)


def clientes_configurados() -> dict:
    """Mapa de chave para nome de cliente, lido de API_KEYS.

    Formato: "chave1:cliente1,chave2:cliente2". Vazio significa acesso aberto,
    que é o padrão da prova de conceito.
    """
    bruto = os.environ.get('API_KEYS', '').strip()
    if not bruto:
        return {}
    mapa = {}
    for par in bruto.split(','):
        if ':' in par:
            chave, nome = par.split(':', 1)
            mapa[chave.strip()] = nome.strip()
    return mapa


class LimitadorDeTaxa:
    """Limite simples de requisições por cliente por minuto.

    Em memória e por processo, o que basta para a prova de conceito. Um serviço
    com várias réplicas precisaria de um contador compartilhado.
    """

    def __init__(self, limite_por_minuto: int):
        self.limite = limite_por_minuto
        self._contagem: dict = {}
        self._trava = threading.Lock()

    def permitido(self, cliente: str, minuto: int) -> bool:
        if self.limite <= 0:
            return True
        with self._trava:
            atual = self._contagem.get(cliente)
            if atual is None or atual[0] != minuto:
                self._contagem[cliente] = [minuto, 1]
                return True
            if atual[1] >= self.limite:
                return False
            atual[1] += 1
            return True
