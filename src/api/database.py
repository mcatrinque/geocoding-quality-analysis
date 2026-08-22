from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from ..env import database_url

# Credenciais vêm do ambiente (.env fora do Docker, variáveis do compose dentro).
SQLALCHEMY_DATABASE_URL = database_url()

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
