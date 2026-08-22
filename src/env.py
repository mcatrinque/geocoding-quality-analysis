"""Configuração de ambiente do repositório de endereços.

As credenciais do banco não são versionadas. Copie `.env.example` para `.env`
e ajuste os valores; este módulo carrega o `.env` (quando `python-dotenv` está
instalado) e monta a URL de conexão a partir das variáveis de ambiente.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    """Carrega o `.env` da raiz do projeto, se houver. Silencioso se ausente."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def database_url() -> str:
    """URL de conexão do PostGIS.

    Usa `DATABASE_URL` quando definida (é o caso dentro do Docker, onde o host
    é `db`); caso contrário monta a URL a partir de POSTGRES_USER, _PASSWORD,
    _DB, _HOST e _PORT. Falha com mensagem acionável se nada estiver definido.
    """
    load_env()

    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DB")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")

    if not (user and password and database):
        raise RuntimeError(
            "Credenciais do banco não configuradas. Copie .env.example para .env "
            "e defina DATABASE_URL (ou POSTGRES_USER, POSTGRES_PASSWORD e POSTGRES_DB)."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"
