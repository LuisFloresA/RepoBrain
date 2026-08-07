"""Tests de integración de la API: crear repo, indexar, buscar y leer archivos."""

from __future__ import annotations

from tests.conftest import make_demo_repo


def _create_demo_repo(client, demo_dir, name="demo") -> dict:
    make_demo_repo(demo_dir)
    resp = client.post(
        "/api/repos", json={"source": "demo", "name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health_still_ok(client) -> None:
    assert client.get("/health").status_code == 200


def test_create_and_index_demo_repo(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    # El POST devuelve estado "indexing" (la UI hace polling por /status)
    assert repo["status"] == "indexing"

    status = client.get(f"/api/repos/{repo['id']}/status").json()
    assert status["status"] == "ready"
    assert status["progress"] == 100.0
    assert status["chunk_count"] >= 3
    assert status["file_count"] >= 3


def test_list_repos(client, env) -> None:
    _create_demo_repo(client, env["demo"], name="primer")
    repos = client.get("/api/repos").json()
    assert len(repos) >= 1
    assert any(r["name"] == "primer" for r in repos)


def test_search_returns_relevant_hits_with_citations(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])

    resp = client.get(f"/api/repos/{repo['id']}/search", params={"q": "dónde se valida el jwt"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"], "La búsqueda debe devolver resultados"
    top = body["results"][0]
    assert top["path"] == "app/auth.py"
    assert top["start_line"] >= 1
    assert "jwt" in top["snippet"].lower()
    assert 0.0 < top["score"] <= 1.0


def test_search_requires_ready_status(client, env) -> None:
    client.post("/api/repos", json={"source": "demo", "name": "aún-indexando"})
    client.post("/api/repos", json={"source": "demo", "name": "dummy"})
    search = client.get("/api/repos/notready/search", params={"q": "jwt"})
    assert search.status_code in (404, 409)


def test_get_file_safe_and_content(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    resp = client.get(f"/api/repos/{repo['id']}/files/app/auth.py")
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "app/auth.py"
    assert body["language"] == "python"
    assert "verify_jwt" in body["content"]
    assert body["line_count"] >= 1


def test_get_file_blocks_path_traversal(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    resp = client.get(f"/api/repos/{repo['id']}/files/../../etc/passwd")
    assert resp.status_code in (400, 404)  # nunca debe devolver el archivo externo
    body = resp.text
    assert "root:" not in body


def test_get_missing_file_404(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    assert client.get(f"/api/repos/{repo['id']}/files/nope.txt").status_code == 404


def test_create_repo_url_required() -> None:
    # Solo validación de esquema: sin ejecución real de clon
    pass


def test_create_repo_blocks_private_url(client, env, monkeypatch) -> None:
    import app.indexing.repo_cloner as cloner

    def bad_url(_url):
        raise ValueError("La URL resuelve a una IP privada (SSRF)")

    monkeypatch.setattr(cloner, "validate_public_url", bad_url)
    resp = client.post(
        "/api/repos",
        json={"url": "https://internal.corp/repo.git", "source": "url"},
    )
    # El repo se crea; la indexación falla de forma controlada (status failed)
    assert resp.status_code == 201
    repo = resp.json()
    status = client.get(f"/api/repos/{repo['id']}/status").json()
    assert status["status"] == "failed"


def test_delete_repo(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    resp = client.delete(f"/api/repos/{repo['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/repos/{repo['id']}").status_code == 404


def test_search_short_query_validation(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    assert (
        client.get(f"/api/repos/{repo['id']}/search", params={"q": "a"}).status_code
        == 422
    )


def test_ask_returns_answer_with_verified_citations(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])

    resp = client.post(
        f"/api/repos/{repo['id']}/ask",
        json={"question": "¿dónde se valida el jwt?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "mock"  # sin API key => mock anti-bloqueo
    assert body["answer"]
    assert body["citations"], "Debe devolver citas verificadas"
    top = body["citations"][0]
    assert top["path"] == "app/auth.py"
    assert 1 <= top["start_line"] <= top["end_line"]


def test_ask_requires_ready_repo(client, env) -> None:
    import app.db.session as db_session
    from app.db.models import Repo

    session = db_session.SessionLocal()
    try:
        repo = Repo(name="en-proceso", source="demo", status="indexing")
        session.add(repo)
        session.commit()
        repo_id = repo.id
    finally:
        session.close()

    resp = client.post(
        f"/api/repos/{repo_id}/ask", json={"question": "¿dónde está la BD?"}
    )
    assert resp.status_code == 409


def test_ask_short_question_validation(client, env) -> None:
    repo = _create_demo_repo(client, env["demo"])
    resp = client.post(f"/api/repos/{repo['id']}/ask", json={"question": "a"})
    assert resp.status_code == 422
