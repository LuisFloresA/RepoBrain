"""Conexión a la base de datos (PostgreSQL vía SQLAlchemy).

Demo embebida de RepoBrain. Busca "¿en qué archivo está la conexión a la BD?".
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://app:secret@db:5432/loginapi"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session():
    """Yields una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
