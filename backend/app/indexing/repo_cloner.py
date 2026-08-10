"""Clonado seguro de repositorios.

- http(s) públicos: SSRF bloqueado (IPs privadas/metadatos). SSH solo a
  github.com/gitlab.com/bitbucket.org (repos privados con deploy key).
- `git clone --depth 1 --no-hardlinks --single-branch`, sin shell.
- El destino se resuelve SIEMPRE dentro del workspace (path traversal).
- El código clonado NUNCA se ejecuta: solo se indexa estáticamente.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.security import git_ssh_env, resolve_within, validate_clone_url


def _clone_command(url: str, dest: str, branch: str | None) -> list[str]:
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--no-hardlinks",
        "--single-branch",
    ]
    if branch:
        cmd += ["--branch", branch]
    return cmd + ["--", url, dest]


def clone_public_repo(url: str, repo_id: str, branch: str | None = None) -> str:
    """Clona `url` dentro del workspace y devuelve el directorio de checkout.

    Si `branch` se omite, git clona la rama por defecto remota. Con `branch`
    se usa `--single-branch --branch <branch>` (solo esa rama, `--depth 1`).
    Las URLs SSH (hosts permitidos) requieren una deploy key en GIT_SSH_KEY.
    """
    url, is_ssh = validate_clone_url(url)
    env = None
    if is_ssh:
        env = git_ssh_env(settings.git_ssh_key)
        if env is None:
            raise ValueError(
                "Repos SSH requieren GIT_SSH_KEY con la ruta de la deploy key"
            )
        env = {**os.environ, **env}

    base = Path(settings.workspace_root).resolve()
    dest = resolve_within(base, repo_id)
    if dest.exists():
        raise ValueError(f"Ya existe un checkout para el repo {repo_id}")

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = _clone_command(url, str(dest), branch)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.git_clone_timeout_seconds,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("El clonado excedió el tiempo permitido") from exc

    if proc.returncode != 0:
        raise ValueError(f"El clonado falló: {proc.stderr.strip()[:300]}")

    resolved = dest.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("El checkout quedó fuera del workspace")
    return str(resolved)
