"""
run_pipeline.py — Pipeline completo da dissertação.

Uso:
  python run_pipeline.py               # roda tudo do início
  python run_pipeline.py --clean       # apaga dados processados e roda tudo
  python run_pipeline.py --reset-env   # recria o venv, limpa dados e roda tudo
  python run_pipeline.py --from nb05    # retoma a partir do NB05
  python run_pipeline.py --from etl --dry-run  # mostra o plano sem executar

Ordem de execução:
  NB01 → NB02 → ETL scripts → NB03 → ... → NB12 → NB15 → NB16 → NB18 → NB22

  --from nb01/nb02 : reinicia ingestão/matching + ETL + análise
  --from etl       : re-executa só os scripts ETL + análise (NB03 em diante)
  --from nb03+     : pula ingestão e ETL, começa na análise
  --com-api        : inclui o NB14 e o NB17, que exigem a API no ar

Nota: NB01 lê o CNEFE de um JSON de 4.6 GB — pode levar 20–30 min na
primeira execução. Execuções subsequentes (--from nb02 em diante) são
rápidas por lerem diretamente de Parquet.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console(highlight=False)

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = BASE_DIR / "requirements.txt"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Pipeline sequence: each tuple is (type, target)
# type "NB"  → run notebook by stem name (auto-resolved in notebooks/)
# type "ETL" → run ETL script by relative path
PIPELINE_STEPS = [
    # As camadas de contexto vem primeiro: o NB02 consome vila_favela.parquet ao
    # estratificar o pareamento, e o ETL que o produz nao depende de notebook
    # algum, apenas dos shapefiles brutos. Com a ordem anterior o pipeline nao
    # rodava do zero, so' sobre uma pasta data/processed ja' povoada.
    ("ETL", "scripts/process_context_layers.py"),
    ("NB", "01_ingestao"),
    ("NB", "02_matching"),
    ("NB", "03_eda_bases"),  # computa CDI/CCR/DRS → cnefe_coordinate_metrics.parquet
    ("NB", "04_lci_completude"),
    (
        "NB",
        "05_acuracia_gci",
    ),  # computa LCI/PCI/GCI → cnefe_master_metrics_base.parquet
    (
        "ETL",
        "scripts/enrich_master_metrics.py",
    ),  # join contextual → cnefe_master_metrics.parquet
    (
        "NB",
        "06_consolidacao_edificios",
    ),  # consolida edifícios → cnefe_edificios.parquet
    ("NB", "07_validacao_gci"),  # validação formal GCI_empirico
    ("NB", "08_eda_contextual"),  # screening de covariáveis → prepara NB09-12
    ("NB", "09_segmentacao_tipologica"),
    ("NB", "10_segmentacao_uso"),
    ("NB", "11_analise_socioespacial"),
    ("NB", "12_determinantes_gci"),
    ("NB", "15_conjuntos_estratos"),  # conjuntos de chaves, estratos e vetores de deslocamento
    ("NB", "16_adjudicacao_cadastral"),  # evidência cadastral da cauda e das ausências
    ("NB", "18_restricao_territorial"),  # concordância de bairro e CEP e restrição territorial
    ("NB", "22_conjuntos_exclusivos"),  # composição das chaves sem par
    ("NB", "23_referencia_municipal_completa"),  # pareamento com todos os pontos do BHMap → cnefe_identidade_completa.parquet
    ("NB", "24_composicao_bases"),  # representação de endereços e estratos nas duas bases
    ("NB", "25_setor_censitario"),  # setor censitário dos pares, restrição por setor e Moran
    ("NB", "26_verificacoes_robustez"),  # candidato mais próximo, borda de setor e de vilas, sensibilidade do Moran
]

# NB14 e NB17 exercitam a API ao vivo e dependem dos servicos no ar
# (docker compose up -d --build + scripts/load_cnefe_to_postgis.py).
# Ficam fora da sequencia padrao para que o pipeline analitico nao dependa
# de infraestrutura externa. Rode-os com --com-api.
PASSO_API = ("NB", "14_api_poc")
PASSO_API_TESTE = ("NB", "17_teste_operacional_independente")

_NOISE = (
    "resource_tracker.py",
    "memmapping_folder",
    "del registry[rtype][name]",
    "~~~~~~~~~~~~~~~",
    "DeprecationWarning: 'asyncio.",
    "asyncio.set_event_loop_policy",
    "asyncio.WindowsSelectorEventLoopPolicy",
    ": DeprecationWarning:",
    "slated for removal in Python 3",
)


def _filter(text: str) -> str:
    lines = [l for l in text.splitlines() if not any(p in l for p in _NOISE)]
    return "\n".join(lines).strip()


def _run(cmd: list) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, _filter(raw)


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


# ── Ambiente ──────────────────────────────────────────────────────────────────


def _install_deps():
    console.print("[dim]  Instalando dependências...[/dim]")
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True,
    )
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        check=True,
        capture_output=True,
    )
    # geobr 0.2.x pins shapely<=2.1.0, but only shapely 2.1.2 has cp314 wheels;
    # the two are API-compatible so --no-deps is safe here
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--no-deps", "geobr"],
        check=True,
        capture_output=True,
    )
    console.print("[green]OK[/green] Dependencias prontas.")


def reset_env():
    if VENV_DIR.exists():
        console.print(f"[dim]  Removendo {VENV_DIR.name}...[/dim]")
        result = subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(VENV_DIR)],
            capture_output=True,
        )
        if result.returncode != 0 or VENV_DIR.exists():
            console.print(
                "[yellow]  ! .venv em uso (VS Code) — recuperando ambiente virtual existente...[/yellow]"
            )
            if VENV_PYTHON.exists():
                try:
                    bak_path = VENV_PYTHON.with_name("python.exe.bak")
                    if bak_path.exists():
                        try:
                            bak_path.unlink()
                        except Exception:
                            pass
                    VENV_PYTHON.rename(bak_path)
                except Exception:
                    pass
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)], capture_output=True
            )
    else:
        console.print("[dim]  Criando ambiente virtual...[/dim]")
        if (
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)]).returncode
            != 0
        ):
            abort("Falha ao criar o ambiente virtual.")
    _install_deps()


# ── Limpeza ───────────────────────────────────────────────────────────────────


def clean_processed():
    import shutil

    removed: dict[str, int] = {}

    files = list(PROCESSED_DIR.glob("*.parquet")) + list(PROCESSED_DIR.glob("*.csv"))
    removed["data/processed"] = len(files)
    for f in files:
        try:
            f.unlink()
        except Exception:
            pass

    for subdir in ["figures", "maps", "tables"]:
        d = BASE_DIR / "outputs" / subdir
        if d.exists():
            items = list(d.iterdir())
            removed[f"outputs/{subdir}"] = len(items)
            for f in items:
                try:
                    if f.is_file():
                        f.unlink()
                    else:
                        shutil.rmtree(f)
                except Exception:
                    pass

    pycaches = list(BASE_DIR.rglob("__pycache__"))
    removed["__pycache__"] = len(pycaches)
    for p in pycaches:
        try:
            shutil.rmtree(p)
        except Exception:
            pass

    parts = "  ".join(
        f"[dim]{k}[/dim] [yellow]{v}[/yellow]" for k, v in removed.items() if v
    )
    console.print(f"  [green]OK[/green] Limpeza  {parts}\n")


# ── Execução de etapas ────────────────────────────────────────────────────────


def run_script(path: str, python: str) -> tuple[bool, str]:
    return _run([python, str(BASE_DIR / path)])


def run_notebook(nb: Path, python: str) -> tuple[bool, str]:
    code = f"""
import asyncio, sys, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import nbformat
from nbclient import NotebookClient
from pathlib import Path

nb_path = Path({repr(str(nb))})
with open(nb_path, encoding="utf-8") as f:
    nb_node = nbformat.read(f, as_version=4)
# O kernel roda com o cwd em notebooks/, que e' onde o Jupyter coloca o
# usuario. Sem isto, caminho relativo escrito na mao funciona na edicao
# interativa e quebra no pipeline.
client = NotebookClient(nb_node, timeout=3600,
                        resources={{"metadata": {{"path": str(nb_path.parent)}}}})
client.reset_execution_trackers()
with client.setup_kernel():
    for i, cell in enumerate(nb_node.cells):
        if cell.cell_type == "code":
            client.execute_cell(cell, i)
with open(nb_path, "w", encoding="utf-8") as f:
    nbformat.write(nb_node, f)
"""
    return _run([python, "-c", code])


# ── Utilitários ───────────────────────────────────────────────────────────────


def abort(msg: str):
    console.print(f"\n[bold red]  ERRO:[/bold red] {msg}")
    sys.exit(1)


def planejar_etapas(inicio: str | None = None, com_api: bool = False) -> list[tuple[str, str]]:
    """Seleciona etapas pelo nome, sem depender da posição na lista."""
    passos = list(PIPELINE_STEPS)
    if com_api:
        passos.extend([PASSO_API, PASSO_API_TESTE])
    if inicio is None or inicio == "01":
        return passos

    contextual = ("ETL", "scripts/process_context_layers.py")
    if inicio == "etl":
        nome_inicial = "03_eda_bases"
    elif inicio == "02":
        nome_inicial = "02_matching"
    else:
        if inicio in {"14", "17"} and not com_api:
            raise ValueError(f"O NB{inicio} exige --com-api. Use: --from nb{inicio} --com-api")
        candidatos = [target for tipo, target in passos if tipo == "NB" and target.startswith(f"{inicio}_")]
        if len(candidatos) != 1:
            raise ValueError(f"Nenhum notebook encontrado para --from nb{inicio}")
        nome_inicial = candidatos[0]

    selecionados: list[tuple[str, str]] = []
    encontrou = False
    for etapa in passos:
        if etapa == ("NB", nome_inicial):
            encontrou = True
        if encontrou:
            selecionados.append(etapa)
    if not encontrou:
        raise ValueError(f"Etapa inicial não encontrada: {nome_inicial}")
    if inicio in {"02", "etl"}:
        if contextual not in passos:
            raise ValueError("O ETL contextual necessário não está no pipeline")
        selecionados.insert(0, contextual)
    return selecionados


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Executa ou mostra o plano do pipeline")
    parser.add_argument("--from", dest="inicio", metavar="ETAPA")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--reset-env", action="store_true")
    parser.add_argument("--com-api", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="mostra as etapas sem executá-las")
    args = parser.parse_args()
    from_val = args.inicio.lower().removeprefix("nb") if args.inicio else None
    if from_val and from_val != "etl":
        from_val = from_val.zfill(2)
    try:
        passos = planejar_etapas(from_val, args.com_api)
    except ValueError as exc:
        parser.error(str(exc))

    if args.dry_run:
        console.print(f"Plano de execução: {len(passos)} etapas")
        for ordem, (tipo, destino) in enumerate(passos, 1):
            console.print(f"{ordem:2d}. {tipo} {destino}")
        return

    do_reset = args.reset_env
    do_clean = args.clean or do_reset

    if do_reset:
        console.rule("[bold]Ambiente")
        reset_env()
        console.print()

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    if do_clean:
        console.rule("[bold]Limpeza")
        clean_processed()

    run_ingestion = from_val is None or from_val in {"01", "02"}

    nb_dir = BASE_DIR / "notebooks"
    steps: list[tuple[str, Path | str]] = []
    for stype, target in passos:
        if stype == "NB":
            nb_path = nb_dir / f"{target}.ipynb"
            steps.append(("NB", nb_path))
        else:
            steps.append(("ETL", target))

    total = len(steps)

    # Validações rápidas
    if not run_ingestion:
        for f in [
            PROCESSED_DIR / "cnefe_bh.parquet",
            PROCESSED_DIR / "bhmap_bh.parquet",
        ]:
            if not f.exists():
                abort(f"{f.name} não encontrado. Execute a partir de NB01: --from nb01")

    console.rule(f"[bold]Pipeline  -  {total} etapas")
    console.print()

    timings: list[tuple[str, str, float]] = []
    wall_start = time.perf_counter()

    for idx, (stype, target) in enumerate(steps, 1):
        label = target.name if isinstance(target, Path) else Path(target).name
        tag = "NB" if stype == "NB" else "ETL"
        desc = f"[dim][{idx}/{total}][/dim]  {label}"

        t0 = time.perf_counter()

        with console.status(f"  {desc}", spinner="dots"):
            if stype == "NB":
                ok, output = run_notebook(target, python)
            else:
                ok, output = run_script(target, python)

        elapsed = time.perf_counter() - t0
        timings.append((tag, label, elapsed))

        tag_color = "cyan" if stype == "NB" else "yellow"
        icon = "[green]OK[/green]" if ok else "[red]X[/red]"
        num = f"[dim][{idx}/{total}][/dim]"

        console.print(
            f"  {icon}  {num}  [{tag_color}]{tag}[/{tag_color}]  "
            f"{label:<48}  [dim]{_fmt_time(elapsed)}[/dim]"
        )

        if not ok:
            if output:
                snippet = output[-4000:] if len(output) > 4000 else output
                console.print(
                    Panel(
                        snippet,
                        title="[red]Saída de erro",
                        border_style="red",
                        padding=(0, 1),
                    )
                )
            if isinstance(target, Path):
                retomada = f"--from nb{target.stem[:2]}"
                if (stype, target.stem) in {PASSO_API, PASSO_API_TESTE}:
                    retomada += " --com-api"
            else:
                retomada = "--from etl"
            abort(f"Falha em {label}. Corrija e retome com {retomada}")

    # ── Resumo ─────────────────────────────────────────────────────────────────
    wall = time.perf_counter() - wall_start
    console.print()
    console.rule("[bold green]Pipeline concluído")

    tbl = Table(
        box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False
    )
    tbl.add_column("Etapa", style="default", no_wrap=True)
    tbl.add_column("Tipo", style="dim", no_wrap=True)
    tbl.add_column("Tempo", style="dim", justify="right", no_wrap=True)

    for tag, lbl, dur in timings:
        color = "cyan" if tag == "NB" else "yellow"
        tbl.add_row(lbl, f"[{color}]{tag}[/{color}]", _fmt_time(dur))

    console.print(tbl)
    mins, secs = divmod(int(wall), 60)
    console.print(f"  [dim]Total  {mins}m {secs}s[/dim]\n")


if __name__ == "__main__":
    main()
