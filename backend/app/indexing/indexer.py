"""Indexación de un directorio de código (parseo estático + troceado)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.security import resolve_within
from app.indexing.chunker import Chunk, chunk_source
from app.indexing.parser import file_is_indexable

SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "coverage",
    "htmlcov",
}


def collect_files(root: str | Path) -> list[tuple[str, Path]]:
    """Lista archivos indexables dentro de `root` con límites de seguridad."""
    base = Path(root).resolve()
    files: list[tuple[str, Path]] = []

    for current in sorted(base.rglob("*")):
        if not current.is_file():
            continue
        rel = str(current.relative_to(base)).replace("\\", "/")
        if any(part in SKIP_DIRS for part in current.parts):
            continue
        if not file_is_indexable(rel):
            continue
        try:
            resolved = resolve_within(base, rel)
        except ValueError:
            continue
        files.append((rel, resolved))
        if len(files) >= settings.max_repo_files:
            break
    return files


def read_source(path: Path) -> str:
    """Lee el archivo respetando el límite de tamaño."""
    if path.stat().st_size > settings.max_file_bytes:
        raise ValueError(f"Archivo demasiado grande: {path.name}")
    return path.read_text(encoding="utf-8", errors="replace")


def index_directory(root: str | Path) -> list[Chunk]:
    """Parsea y trocea todos los archivos indexables de `root`."""
    chunks: list[Chunk] = []
    for rel, abs_path in collect_files(root):
        try:
            source = read_source(abs_path)
        except (OSError, ValueError):
            continue
        chunks.extend(chunk_source(rel, source))
    return chunks
