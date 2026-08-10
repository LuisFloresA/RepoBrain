"""Sesión SQLite y helpers de la base de datos."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base


def build_engine():
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Migración ligera para SQLite: añade columnas nuevas si no existen.

    `create_all` no altera tablas existentes; el añadido de columnas en
    modelos (p. ej. `branch`, métricas de indexado) se aplica aquí manteniendo
    los datos del demo.
    """
    added = [
        "branch",
        "source_rev",
        "indexed_files",
        "skipped_files",
        "indexed_bytes",
        "last_indexed_at",
        "stats",
        "last_changes",
    ]
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        existing = {c["name"] for c in inspector.get_columns("repos")}
    except Exception:
        return
    missing = [col for col in added if col not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        for col in missing:
            coltype = "TEXT" if col in {"branch", "source_rev", "last_indexed_at"} else "INTEGER"
            if col in {"stats", "last_changes"}:
                coltype = "TEXT"
            conn.execute(text(f"ALTER TABLE repos ADD COLUMN {col} {coltype}"))


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
