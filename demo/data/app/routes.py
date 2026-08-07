"""Rutas HTTP de la API de login.

Demo embebida de RepoBrain.
"""

from fastapi import Depends, HTTPException, status

from app.auth import verify_jwt
from app.db import get_db_session
from app.models import User


def get_current_user(authorization: str) -> User:
    """Dependencia de FastAPI que exige un JWT válido en el header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = authorization.removeprefix("Bearer ")
    payload = verify_jwt(token)
    return payload


def create_account(email: str, password: str, db=Depends(get_db_session)) -> User:
    user = User(email=email, password_hash=password)
    db.add(user)
    db.commit()
    return user
