from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)
engine = None


def configure_engine(database_url: str | None = None):
    global engine

    if engine is not None:
        engine.dispose()

    url = database_url or get_settings().database_url
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, future=True, **kwargs)
    SessionLocal.configure(bind=engine)
    return engine


def dispose_engine() -> None:
    global engine
    if engine is not None:
        engine.dispose()
        engine = None


def init_db() -> None:
    from app import models  # noqa: F401

    if engine is None:
        configure_engine()
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


configure_engine()
