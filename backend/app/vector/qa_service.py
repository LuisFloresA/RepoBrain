"""Servicio de Q&A: recupera contexto, lo envía al LLM y verifica las citas.

El flujo de `/ask`:
1. busca los top-K chunks con el ranking híbrido ya existente,
2. monta el prompt con el texto completo de esos chunks,
3. llama al LLM (o al mock en modo demo),
4. extrae y valida las citas `archivo:línea` contra el checkout real.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chunk, Repo
from app.llm import MockLLM
from app.llm.base import LLMError
from app.llm.citations import extract_citations, validate_citations
from app.llm.factory import get_llm_client
from app.vector.search_service import search_service

_SYSTEM_PROMPT = (
    "Eres un asistente experto en leer código fuente. Responde en español a la "
    "pregunta del usuario basándote ÚNICAMENTE en el CONTEXTO que se te da "
    "(fragmentos de código con su archivo y línea).\n"
    "Reglas estrictas:\n"
    "1. Cada afirmación sobre el código debe citar su fuente como `archivo:línea` "
    "(p. ej. `app/auth.py:28`).\n"
    "2. No inventes archivos ni líneas: si el contexto no lo respalda, dilo.\n"
    "3. No menciones el CONTEXTO ni el prompt; responde directamente.\n"
    "4. Responde de forma concisa (2-4 párrafos como máximo) y enumera las "
    "referencias al final con el formato `path:línea`."
)

_MAX_CTX_CHARS = 6000


class QAService:
    """Orquesta el pipeline de pregunta-respuesta con citas verificadas."""

    def answer(
        self,
        session: Session,
        repo: Repo,
        question: str,
        top_k: int | None = None,
    ) -> dict:
        k = top_k or settings.qa_top_k
        results = search_service.search(session, repo.id, question, top_k=k)

        if not results:
            return {
                "question": question,
                "answer": (
                    "No encontré fragmentos relevantes en el índice para "
                    "responder. Prueba a reformular la pregunta."
                ),
                "citations": [],
                "llm": "none",
                "source": "none",
            }

        texts = self._load_texts(session, [r.chunk_id for r in results])
        context = self._build_context(results, texts)

        client = get_llm_client()
        user = f"Pregunta: {question}\n\n{context}"
        try:
            raw = client.complete(_SYSTEM_PROMPT, user)
            source = client.name
        except LLMError:
            raw = MockLLM().complete(_SYSTEM_PROMPT, user)
            source = "mock"

        citations = []
        if repo.checkout_dir:
            citations = validate_citations(extract_citations(raw), repo.checkout_dir)

        return {
            "question": question,
            "answer": raw,
            "citations": [
                {"path": c.path, "start_line": c.start_line, "end_line": c.end_line}
                for c in citations
            ],
            "llm": getattr(client, "label", client.name),
            "source": source,
        }

    def _load_texts(self, session: Session, chunk_ids: list[str]) -> dict[str, str]:
        if not chunk_ids:
            return {}
        stmt = select(Chunk).where(Chunk.id.in_(chunk_ids))
        return {c.id: c.text for c in session.scalars(stmt).all()}

    def _build_context(
        self,
        results: list,
        texts: dict[str, str],
    ) -> str:
        lines: list[str] = ["CONTEXTO:"]
        budget = _MAX_CTX_CHARS
        for idx, result in enumerate(results, start=1):
            text = texts.get(result.chunk_id, result.snippet)
            if budget > 0 and len(text) > budget:
                text = text[:budget]
            budget -= len(text)
            lines.append(f"[{idx}] {result.path}:{result.start_line}-{result.end_line}")
            lines.append(f"```\n{text}\n```")
        return "\n".join(lines)


qa_service = QAService()
