from src.api.metering import Contabilizador, Registro


def test_contabilizador_reinicia_sem_perder_registros(monkeypatch):
    contabilizador = Contabilizador(None, intervalo_s=.01)
    gravados = []
    monkeypatch.setattr(contabilizador, '_gravar', lambda lote: gravados.extend(lote))
    for i in range(2):
        contabilizador.iniciar()
        contabilizador.iniciar()
        contabilizador.registrar(Registro('/geocode', 'POST', 200, i, 'teste'))
        contabilizador.encerrar()
        assert not contabilizador._thread.is_alive()
    assert [r.latencia_ms for r in gravados] == [0,1]
    assert contabilizador.descartados == 0
    assert contabilizador.pendentes == 0
