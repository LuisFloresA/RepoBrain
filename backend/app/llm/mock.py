"""Mock de LLM para el modo demo (sin API key ni red).

Genera una respuesta plantilla a partir del fragmento mejor rankeado del
contexto, con la cita `archivo:línea`. Asi el pipeline de `/ask` se
demuestra de punta a punta sin depender de un proveedor pagado.
"""

from __future__ import annotations

import re

from .base import LLMClient

_CONTEXT_RE = re.compile(r"^\[(\d+)\] (\S+):(\d+)(?:-\d+)?$", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"```\w*\n(.*?)```", re.DOTALL)


def _split_blocks(user_prompt: str) -> list[tuple[str, int, str]]:
    """Extrae (path, line, code) de los bloques `[n] path:line ... ```code````."""
    blocks: list[tuple[str, int, str]] = []
    parts = _CODE_BLOCK_RE.split(user_prompt)
    # parts = [text, code, text, code, ...] -> pares (header, code)
    for i in range(1, len(parts), 2):
        header = parts[i - 1]
        code = parts[i]
        match = _CONTEXT_RE.search(header)
        if not match:
            continue
        blocks.append((match.group(2), int(match.group(3)), code.strip()))
    return blocks


class MockLLM(LLMClient):
    """Responde con una plantilla basada en el top-1 chunk del contexto."""

    name = "mock"

    def complete(self, system: str, user: str) -> str:
        blocks = _split_blocks(user)
        if not blocks:
            return (
                "No encontré fragmentos relevantes para responder. "
                "Prueba reformular la pregunta o indexar más código."
            )
        path, line, code = blocks[0]
        head = code.splitlines()
        shown = "\n".join(head[:6])
        return (
            f"He revisado el código y la respuesta está en **{path}:{line}**.\n\n"
            f"```\n{shown}\n```\n\n"
            f"El fragmento de {path}:{line} es el que mejor responde a la "
            f"pregunta: {_first_line(user)}. Revisa {path}:{line} y el código "
            f"alrededor para el detalle completo."
        )


def _first_line(user_prompt: str) -> str:
    line = user_prompt.splitlines()[0] if user_prompt else ""
    return line.replace("Pregunta:", "").strip()[:120]
