"""Indexación de un directorio de código (parseo estático + troceado).

Devuelve `IndexResult` con los chunks y estadísticas de cobertura (archivos
indexados por lenguaje, omitidos por extensión no soportada / tamaño, bytes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


def _walk(root: Path) -> list[Path]:
    files: list[Path] = []
    for current in sorted(root.rglob("*")):
        if not current.is_file():
            continue
        if any(part in SKIP_DIRS for part in current.parts):
            continue
        files.append(current)
        if len(files) >= settings.max_repo_files:
            break
    return files


def collect_files(root: str | Path) -> list[tuple[str, Path]]:
    """Lista archivos indexables dentro de `root` con límites de seguridad."""
    base = Path(root).resolve()
    selected: list[tuple[str, Path]] = []
    for current in _walk(base):
        rel = str(current.relative_to(base)).replace("\\", "/")
        if not file_is_indexable(rel):
            continue
        try:
            resolved = resolve_within(base, rel)
        except ValueError:
            continue
        if resolved.is_file():
            selected.append((rel, resolved))
    return selected


def read_source(path: Path) -> str:
    """Lee el archivo respetando el límite de tamaño."""
    if path.stat().st_size > settings.max_file_bytes:
        raise ValueError(f"Archivo demasiado grande: {path.name}")
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass
class IndexResult:
    chunks: list[Chunk] = field(default_factory=list)
    by_language: dict[str, int] = field(default_factory=dict)
    indexed_bytes: int = 0
    skipped_total: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


def _make_result(chunks: list[Chunk], skipped: dict[str, int]) -> IndexResult:
    language_set: set[str] = set()
    by_language: dict[str, int] = {}
    bytes_indexed = 0
    files: list[str] = []
    for chunk in chunks:
        lang = chunk.language or "unknown"
        by_language[lang] = by_language.get(lang, 0) + 1
        if chunk.path not in language_set:
            language_set.add(chunk.path)
            files.append(chunk.path)
        bytes_indexed += len(chunk.text.encode("utf-8"))
    total_skipped = sum(skipped.values())
    return IndexResult(
        chunks=chunks,
        by_language=by_language,
        indexed_bytes=bytes_indexed,
        skipped_total=total_skipped,
        skipped_reasons=skipped,
        files=files,
    )


def index_directory(
    root: str | Path, paths: list[str] | None = None
) -> IndexResult:
    """Parsea y trocea los archivos de `root`.

    Con `paths` se indexan SOLO esos relativos (indexación incremental);
    en caso contrario se indexa todo el árbol.
    """
    base = Path(root).resolve()
    skipped: dict[str, int] = {"sin_lenguaje": 0, "demasiado_grande": 0, "error_lectura": 0}
    chunks: list[Chunk] = []
    sources: list[tuple[str, Path]] = []

    if paths is not None:
        for rel in paths:
            rel_norm = rel.replace("\\", "/")
            if not file_is_indexable(rel_norm):
                skipped["sin_lenguaje"] += 1
                continue
            try:
                resolved = resolve_within(base, rel_norm)
            except ValueError:
                continue
            if resolved.is_file():
                sources.append((rel_norm, resolved))
            else:
                skipped["error_lectura"] += 1
    else:
        for abs_path in _walk(base):
            rel = str(abs_path.relative_to(base)).replace("\\", "/")
            if not file_is_indexable(rel):
                skipped["sin_lenguaje"] += 1
                continue
            sources.append((rel, abs_path))

    for rel, abs_path in sources:
        try:
            source = read_source(abs_path)
        except (OSError, ValueError) as exc:
            reason = "demasiado_grande" if "grande" in str(exc) else "error_lectura"
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        chunks.extend(chunk_source(rel, source))

    return _make_result(chunks, skipped)