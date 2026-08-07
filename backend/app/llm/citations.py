"""Extracción y validación de citas `archivo:línea` de una respuesta LLM.

La validación contra el repo real (el archivo existe y la línea cabe en el
archivo) evita que el modelo cite fragmentos que no existen (alucinación).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.security import resolve_within

_CITE_RE = re.compile(
    r"([A-Za-z0-9_./-]+\.(?:py|js|ts|jsx|tsx|cs|java)):(\d+)"
)

_MAX_CITATIONS = 8


@dataclass
class Citation:
    path: str
    start_line: int
    end_line: int


def extract_citations(text: str) -> list[tuple[str, int]]:
    """Extrae (path, line) únicos de un texto, conservando el orden."""
    pairs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _CITE_RE.finditer(text):
        pair = (match.group(1), int(match.group(2)))
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
        if len(pairs) >= _MAX_CITATIONS:
            break
    return pairs


def validate_citations(
    pairs: list[tuple[str, int]], checkout_dir: str | Path
) -> list[Citation]:
    """Filtra citas a las que existen realmente en el checkout del repo."""
    base = Path(checkout_dir).resolve()
    valid: list[Citation] = []
    for path, line in pairs:
        if line < 1:
            continue
        try:
            file_path = resolve_within(base, path)
        except ValueError:
            continue
        if not file_path.is_file():
            continue
        if file_path.stat().st_size > 4 * 1024 * 1024:
            continue
        try:
            line_count = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if line > line_count:
            continue
        end = min(line + 2, line_count)
        valid.append(Citation(path=path, start_line=line, end_line=end))
    return valid
