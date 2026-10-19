"""Engine / session / Base.

Defaults to a local SQLite file so the project runs with zero setup. Point it at
Postgres (as the plan specifies, and as docker-compose does) by exporting:
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/sitepulse
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _normalize(url: str) -> str:
    """Managed Postgres (Railway, Render, Heroku-style) hands out a bare
    `postgres://` or `postgresql://` URL. SQLAlchemy then picks psycopg2 by
    default, which isn't installed here (we ship psycopg3, `psycopg[binary]`
    in requirements.txt) -- it fails at connect time with a driver error, not
    at import time, so it's easy to ship and only notice in production.
    Force the psycopg3 dialect unless the URL already names one."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize(os.getenv("DATABASE_URL", "sqlite:///./delivery.db"))

# SQLite needs this flag to be usable across FastAPI's threads.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_session():
    """FastAPI dependency: yield a session, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. Imports models so the mappers are registered first."""
    import db.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
