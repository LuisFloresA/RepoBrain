"""Troceado de código en chunks de ~512 tokens, alineados a definiciones."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.indexing.parser import extract_anchors, language_for_path

_WORD_RE = re.compile(r"\S+")


def estimate_tokens(text: str) -> int:
    """Estimación burda de tokens (palabras + signos de puntuación)."""
    words = len(_WORD_RE.findall(text))
    punct = sum(1 for c in text if c in "{}();,[]:" and c != " ")
    return max(words, punct // 2) or 1


@dataclass
class Chunk:
    path: str
    language: str | None
    start_line: int
    end_line: int
    text: str

    @property
    def token_count(self) -> int:
        return estimate_tokens(self.text)


def _split_long_line(
    line: str, start_line: int, max_tokens: int
) -> list[tuple[int, int, str]]:
    """Divide una línea que sola excede max_tokens en ventanas de palabras."""
    words = line.split(" ")
    windows: list[tuple[int, int, str]] = []
    current: list[str] = []
    current_tokens = 0
    for word in words:
        tokens = max(estimate_tokens(word), 1)
        if current and current_tokens + tokens > max_tokens:
            windows.append((start_line, start_line, " ".join(current)))
            current = []
            current_tokens = 0
        current.append(word)
        current_tokens += tokens
    if current:
        windows.append((start_line, start_line, " ".join(current)))
    return windows


def _split_by_lines(
    lines: list[str], start_line: int, max_tokens: int, max_lines: int
) -> list[tuple[int, int, str]]:
    """Trocea `lines` (ya desplazadas) en ventanas que respeten máximos."""
    windows: list[tuple[int, int, str]] = []
    current: list[str] = []
    current_start = start_line
    current_tokens = 0

    for i, line in enumerate(lines):
        line_tokens = estimate_tokens(line)
        if line_tokens > max_tokens:
            if current:
                windows.append((current_start, start_line + i - 1, "\n".join(current)))
                current = []
                current_tokens = 0
            windows.extend(_split_long_line(line, start_line + i, max_tokens))
            current_start = start_line + i + 1
            continue
        if (
            current
            and (current_tokens + line_tokens > max_tokens or len(current) >= max_lines)
        ):
            windows.append(
                (current_start, start_line + i - 1, "\n".join(current))
            )
            current = []
            current_start = start_line + i
            current_tokens = 0
        current.append(line)
        current_tokens += line_tokens

    if current:
        windows.append((current_start, start_line + len(lines) - 1, "\n".join(current)))
    return windows


def chunk_source(
    path: str,
    source: str,
    *,
    max_tokens: int = 512,
    max_lines: int = 200,
    use_anchors: bool = True,
) -> list[Chunk]:
    """Trocea el source en chunks. Los anchors (definiciones) guían el corte."""
    language = language_for_path(path)
    lines = source.splitlines()
    if not lines:
        return []

    anchors: list[int] = []
    if use_anchors and language:
        anchors = extract_anchors(source, language)

    segments: list[tuple[int, int, str]] = []
    if anchors:
        first = anchors[0]
        if first > 1:
            # Prefijo del archivo antes del primer anchor (docstring, imports, config)
            segments.append((1, first - 1, "\n".join(lines[: first - 1])))
        for i, anchor in enumerate(anchors):
            seg_start = anchor
            seg_end = anchors[i + 1] - 1 if i + 1 < len(anchors) else len(lines)
            text = "\n".join(lines[seg_start - 1 : seg_end])
            segments.append((seg_start, seg_end, text))
    else:
        segments = _split_by_lines(lines, 1, max_tokens, max_lines)

    chunks: list[Chunk] = []
    for start, end, text in segments:
        if estimate_tokens(text) > max_tokens:
            sub = _split_by_lines(
                text.splitlines(), start, max_tokens, max_lines
            )
            for s_start, s_end, s_text in sub:
                chunks.append(Chunk(path, language, s_start, s_end, s_text))
        else:
            chunks.append(Chunk(path, language, start, end, text))

    return [c for c in chunks if c.text.strip()]
