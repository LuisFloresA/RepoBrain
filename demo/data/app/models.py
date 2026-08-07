"""Modelos con soft delete.

Demo embebida de RepoBrain. Busca "¿cómo se hace el soft delete?".
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.db import engine

Base = sessionmaker(bind=engine).class_

class_ = Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def soft_delete(self) -> None:
        """Marca la fila como borrada sin eliminarla físicamente."""
        self.deleted_at = datetime.now(timezone.utc)
        self.is_active = False

    @classmethod
    def active(cls, query):
        return query.filter(cls.deleted_at.is_(None))
