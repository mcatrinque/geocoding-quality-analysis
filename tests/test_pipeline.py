"""Seleção de etapas e plano sem executar o pipeline."""

import sys

import pytest

import run_pipeline


def test_retomada_etl_inclui_contexto_e_analise_sem_ingestao():
    plano = run_pipeline.planejar_etapas("etl")
    assert plano[0] == ("ETL", "scripts/process_context_layers.py")
    assert plano[1] == ("NB", "03_eda_bases")
    assert ("ETL", "scripts/enrich_master_metrics.py") in plano
    assert ("NB", "01_ingestao") not in plano
    assert ("NB", "02_matching") not in plano


def test_retomada_etl_independe_da_posicao_do_contexto(monkeypatch):
    passos = list(run_pipeline.PIPELINE_STEPS)
    contexto = ("ETL", "scripts/process_context_layers.py")
    passos.remove(contexto)
    passos.insert(2, contexto)
    monkeypatch.setattr(run_pipeline, "PIPELINE_STEPS", passos)
    plano = run_pipeline.planejar_etapas("etl")
    assert plano[0] == contexto
    assert plano[1] == ("NB", "03_eda_bases")


def test_retomada_nb02_inclui_pre_requisito_contextual():
    plano = run_pipeline.planejar_etapas("02")
    assert plano[:2] == [
        ("ETL", "scripts/process_context_layers.py"),
        ("NB", "02_matching"),
    ]
    assert ("NB", "01_ingestao") not in plano


def test_retomada_nb14_exige_api():
    with pytest.raises(ValueError, match="com-api"):
        run_pipeline.planejar_etapas("14")
    assert run_pipeline.planejar_etapas("14", com_api=True) == [run_pipeline.PASSO_API, run_pipeline.PASSO_API_TESTE]


def test_dry_run_nao_limpa_nem_executa(monkeypatch, capsys):
    def proibido(*args, **kwargs):
        raise AssertionError("O plano não pode executar ou limpar artefatos")

    for nome in ("reset_env", "clean_processed", "run_script", "run_notebook"):
        monkeypatch.setattr(run_pipeline, nome, proibido)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_pipeline.py", "--from", "etl", "--dry-run", "--clean", "--reset-env"],
    )
    run_pipeline.main()
    saida = capsys.readouterr().out
    assert "scripts/process_context_layers.py" in saida
    assert "03_eda_bases" in saida
    assert "01_ingestao" not in saida
