"""Configuration de la connexion PostgreSQL avec SQLAlchemy."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ehm_user:ehm_password@localhost:5432/ehm_db",
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency FastAPI : fournit une session DB par requete."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
