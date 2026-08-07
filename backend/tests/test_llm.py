"""Tests del módulo LLM: mock, cliente OpenAI-compatible y citas validadas."""

from __future__ import annotations

import io
import urllib.error

import pytest

from app.llm.base import LLMError
from app.llm.citations import extract_citations, validate_citations
from app.llm.factory import get_llm_client
from app.llm.mock import MockLLM
from app.llm.openai import OpenAICompatClient


def _user_prompt(question: str = "¿dónde se valida el jwt?") -> str:
    return (
        f"Pregunta: {question}\n\n"
        "CONTEXTO:\n"
        "[1] app/auth.py:3-5\n"
        "```\n"
        "def verify_jwt(token):\n"
        "    return jwt.decode(token, SECRET_KEY)\n"
        "```\n"
    )


def test_mock_llm_returns_template_with_citation() -> None:
    answer = MockLLM().complete("system", _user_prompt())
    assert "app/auth.py:3" in answer
    assert "verify_jwt" in answer


def test_mock_llm_without_context_returns_fallback() -> None:
    answer = MockLLM().complete("system", "Pregunta: hola")
    assert "No encontré fragmentos" in answer


def test_openai_client_posts_chat_completions(monkeypatch) -> None:
    client = OpenAICompatClient(
        api_key="k", model="m", base_url="https://api.example.com/v1"
    )
    captured: dict = {}

    def fake_post_json(url: str, payload: dict):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "respuesta"}}]}

    monkeypatch.setattr(client, "_post_json", fake_post_json)
    assert client.complete("sys", "usr") == "respuesta"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["payload"]["model"] == "m"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][1]["content"] == "usr"


def test_openai_client_raises_on_malformed_response(monkeypatch) -> None:
    client = OpenAICompatClient(api_key="k", model="m", base_url="https://x/v1")

    def fake_post_json(url: str, payload: dict):
        return {"no": "choices"}

    monkeypatch.setattr(client, "_post_json", fake_post_json)
    with pytest.raises(LLMError):
        client.complete("sys", "usr")


def test_openai_client_http_error_becomes_llmerror(monkeypatch) -> None:
    client = OpenAICompatClient(api_key="k", model="m", base_url="https://x/v1")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            "https://x/v1/chat/completions", 401, "Unauthorized", {}, io.BytesIO(b"{}")
        )

    import app.llm.openai as openai_mod

    monkeypatch.setattr(openai_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(LLMError):
        client.complete("sys", "usr")


def test_extract_citations_parses_and_dedupes() -> None:
    text = (
        "Mira app/auth.py:28 y web/api.js:3. Además app/auth.py:28 de nuevo "
        "y un falso app/readme:99"
    )
    pairs = extract_citations(text)
    assert ("app/auth.py", 28) in pairs
    assert ("web/api.js", 3) in pairs
    assert pairs.count(("app/auth.py", 28)) == 1


def test_validate_citations_keeps_only_existing_lines(tmp_path) -> None:
    repo_dir = tmp_path / "checkout"
    (repo_dir / "app").mkdir(parents=True)
    (repo_dir / "app" / "auth.py").write_text("a\nb\nc\nd\ne\n")

    valid = validate_citations(
        [("app/auth.py", 3), ("app/auth.py", 99), ("missing.py", 1)],
        repo_dir,
    )
    assert len(valid) == 1
    assert valid[0].path == "app/auth.py"
    assert valid[0].start_line == 3


def test_validate_citations_blocks_path_traversal(tmp_path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("x\n")
    valid = validate_citations([("../outside.txt", 1)], tmp_path)
    assert valid == []


def test_get_llm_client_defaults_to_mock(env) -> None:
    assert isinstance(get_llm_client(), MockLLM)


def test_get_llm_client_uses_openai_with_key(env, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    client = get_llm_client()
    assert isinstance(client, OpenAICompatClient)
    assert client.label == "openai:gpt-4o-mini"
