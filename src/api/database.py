"""Conexão com o repositório de endereços.

O pool é dimensionado para um serviço, e não para um script: conexões são caras
no PostgreSQL e a API responde muitas consultas curtas. `pool_pre_ping` evita
que uma conexão derrubada pelo banco cause erro na primeira requisição depois
de um período ocioso.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from ..env import database_url

SQLALCHEMY_DATABASE_URL = database_url()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=int(os.environ.get('DB_POOL_SIZE', 10)),
    max_overflow=int(os.environ.get('DB_MAX_OVERFLOW', 20)),
    pool_timeout=int(os.environ.get('DB_POOL_TIMEOUT', 30)),
    pool_recycle=int(os.environ.get('DB_POOL_RECYCLE', 1800)),
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
