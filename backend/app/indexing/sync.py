"""Sincronización incremental de un checkout existente (git diff).

Actualiza el clone a la última versión y devuelve qué cambió (paths +
estado + mensajes de commit), para re-indexar solo los archivos afectados.
El código del repo NUNCA se ejecuta: solo git y parseo estático.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings

_STATUS_LABELS = {
    "A": "añadido",
    "M": "modificado",
    "D": "eliminado",
    "R": "renombrado",
    "C": "copiado",
    "T": "tipo cambiado",
}


class SyncError(Exception):
    """Error controlado durante la sincronización git."""


def _run_git(checkout: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(checkout),
        capture_output=True,
        text=True,
        timeout=settings.git_clone_timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise SyncError(proc.stderr.strip()[:300])
    return proc.stdout.strip()


@dataclass
class SyncResult:
    is_full: bool = False
    paths: list[str] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)
    commits: list[str] = field(default_factory=list)
    from_rev: str | None = None
    to_rev: str | None = None


def sync_checkout(url: str, branch: str | None, checkout: str) -> SyncResult:
    """Trae el último commit de `url` a `checkout` y describe los cambios.

    - checkout inexistente/roto -> SyncResult(is_full=True): re-clonar.
    - sin red o git roto      -> SyncResult(is_full=True): re-escaneo local.
    - sin cambios             -> paths vacíos, commits vacíos.
    """
    path = Path(checkout)
    if not path.is_dir():
        return SyncResult(is_full=True)

    try:
        base_rev = _run_git(path, "rev-parse", "HEAD")
    except SyncError:
        return SyncResult(is_full=True)

    fetch_args = ["fetch", "origin", "--depth", "1"]
    if branch:
        fetch_args.append(branch)
    try:
        _run_git(path, *fetch_args)
        to_rev = _run_git(path, "rev-parse", "FETCH_HEAD")
    except SyncError:
        # Sin red: no se puede comparar; re-escaneo completo del checkout local.
        return SyncResult(is_full=True, from_rev=base_rev, to_rev=base_rev)

    if base_rev == to_rev:
        return SyncResult(from_rev=base_rev, to_rev=to_rev)

    statuses: dict[str, str] = {}
    commits: list[str] = []
    try:
        status_text = _run_git(
            path, "diff", "--name-status", "--diff-filter=ACDMRTUXB", "HEAD", "FETCH_HEAD"
        )
        for line in status_text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                code = parts[0][0]
                statuses[parts[1]] = _STATUS_LABELS.get(code, "cambiado")
        log = _run_git(path, "log", "--oneline", "-10", f"HEAD..{to_rev}")
        commits = [line for line in log.splitlines() if line]
    except SyncError:
        statuses = {}
        commits = []

    is_full = len(statuses) > settings.incremental_max_changed
    try:
        _run_git(path, "reset", "--hard", "--quiet", "FETCH_HEAD")
    except SyncError:
        is_full = True

    return SyncResult(
        is_full=is_full,
        paths=list(statuses),
        statuses=statuses,
        commits=commits,
        from_rev=base_rev,
        to_rev=to_rev,
    )