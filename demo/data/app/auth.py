"""Autenticación con JWT: validación y firma de tokens.

Demo embebida de RepoBrain. Busca "¿dónde se valida el JWT?".
"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

SECRET_KEY = "dev-secret-change-me"
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = 30


def create_token(subject: str, role: str = "user") -> str:
    """Firma un JWT con expiración y rol."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_jwt(token: str) -> dict:
    """Valida el JWT: firma, expiración y claims. Lanza InvalidTokenError si falla."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("role") not in {"user", "admin"}:
        raise InvalidTokenError("Rol no permitido")
    return payload
