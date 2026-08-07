"""Clonado seguro de repositorios públicos.

- Solo URLs http(s) públicas (SSRF bloqueado: IPs privadas/metadatos).
- `git clone --depth 1 --no-hardlinks --single-branch`, sin shell.
- El destino se resuelve SIEMPRE dentro del workspace (path traversal).
- El código clonado NUNCA se ejecuta: solo se indexa estáticamente.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.security import resolve_within, validate_public_url


def clone_public_repo(url: str, repo_id: str) -> str:
    """Clona `url` dentro del workspace y devuelve el directorio de checkout."""
    validate_public_url(url)

    base = Path(settings.workspace_root).resolve()
    dest = resolve_within(base, repo_id)
    if dest.exists():
        raise ValueError(f"Ya existe un checkout para el repo {repo_id}")

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--no-hardlinks",
        "--single-branch",
        "--",
        url,
        str(dest),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.git_clone_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("El clonado excedió el tiempo permitido") from exc

    if proc.returncode != 0:
        raise ValueError(f"El clonado falló: {proc.stderr.strip()[:300]}")

    resolved = dest.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("El checkout quedó fuera del workspace")
    return str(resolved)
