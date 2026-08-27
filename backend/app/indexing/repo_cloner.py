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
from typing import Any

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


def list_remote_branches(url: str) -> dict[str, Any]:
    """Consulta las ramas remotas de `url` usando `git ls-remote --heads --symref`.

    Devuelve un diccionario con `url`, `default_branch` y lista de `branches`.
    Valida la URL contra SSRF y restricciones SSH.
    """
    clean_url, is_ssh = validate_clone_url(url)
    env = None
    if is_ssh:
        env = git_ssh_env(settings.git_ssh_key)
        if env is None:
            raise ValueError(
                "Repos SSH requieren GIT_SSH_KEY con la ruta de la deploy key"
            )
        env = {**os.environ, **env}

    cmd = ["git", "ls-remote", "--heads", "--symref", "--", clean_url]
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
        raise ValueError("Tiempo de espera agotado al consultar ramas remotas") from exc

    if proc.returncode != 0:
        err = proc.stderr.strip()[:300] or "No se pudo acceder al repositorio remoto"
        raise ValueError(f"Error al consultar ramas: {err}")

    default_branch: str | None = None
    branches: list[str] = []
    seen: set[str] = set()

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Detección de rama por defecto: "ref: refs/heads/main\tHEAD"
        if line.startswith("ref: refs/heads/") and "HEAD" in line:
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith("ref: refs/heads/"):
                default_branch = parts[0][len("ref: refs/heads/"):]
        elif "refs/heads/" in line:
            ref = line.split("refs/heads/")[-1].strip()
            if ref and ref not in seen:
                seen.add(ref)
                branches.append(ref)

    branches.sort()
    if default_branch and default_branch in branches:
        branches.remove(default_branch)
        branches.insert(0, default_branch)
    elif branches and not default_branch:
        for candidate in ("main", "master"):
            if candidate in branches:
                default_branch = candidate
                branches.remove(candidate)
                branches.insert(0, candidate)
                break
        if not default_branch and branches:
            default_branch = branches[0]

    return {
        "url": url,
        "default_branch": default_branch,
        "branches": branches,
    }
