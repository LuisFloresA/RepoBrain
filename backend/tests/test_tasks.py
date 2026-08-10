"""Tests end-to-end de la tarea de indexación (incremental y lenguajes)."""

from __future__ import annotations

from pathlib import Path

from tests.test_sync import _clone, _init_remote, _push_from
from workers.tasks import index_repo


def _run(repo_id: str) -> dict:
    return index_repo(repo_id)


def test_incremental_task_tracks_changes(env, tmp_path: Path) -> None:
    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    _push_from(
        remote,
        tmp_path,
        {"app.py": "x = 2\n", "new/lib.py": "def helper():\n    return 1\n"},
        "evolucion",
    )

    import app.db.session as db_session
    from app.db.models import Repo

    session = db_session.SessionLocal()
    try:
        repo = Repo(
            name="incremental",
            source="url",
            url=str(remote),
            checkout_dir=str(work),
            status="created",
        )
        session.add(repo)
        session.commit()
        repo_id = repo.id
    finally:
        session.close()

    result = _run(repo_id)
    assert result["status"] == "ready"

    session = db_session.SessionLocal()
    try:
        repo = session.get(Repo, repo_id)
        assert repo is not None
        assert repo.chunk_count >= 2
        assert repo.stats and repo.stats["by_language"].get("python") == 2
        changes = repo.last_changes or {}
        assert changes["full"] is False
        by_path = {c["path"]: c["status"] for c in changes["files"] or []}
        assert by_path.get("app.py") == "modificado"
        assert by_path.get("new/lib.py") == "añadido"
        assert changes["commits"]
    finally:
        session.close()


def test_incremental_no_changes_preserves_coverage(env, tmp_path: Path) -> None:
    """Re-index sin cambios NO debe borrar las métricas de cobertura."""

    def _mk_repo(checkout_dir: str | None, name: str, remote: Path) -> str:
        import app.db.session as db_session
        from app.db.models import Repo

        session = db_session.SessionLocal()
        try:
            repo = Repo(
                name=name,
                source="url",
                url=str(remote),
                checkout_dir=checkout_dir,
                status="ready",
                file_count=2,
                indexed_files=2,
                skipped_files=1,
                indexed_bytes=4104,
                stats={"by_language": {"python": 2}, "skipped_reasons": {}},
            )
            session.add(repo)
            session.commit()
            return repo.id
        finally:
            session.close()

    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    repo_id = _mk_repo(str(work), "sin-cambios", remote)

    result = _run(repo_id)
    assert result["status"] == "ready"

    import app.db.session as db_session
    from app.db.models import Repo

    session = db_session.SessionLocal()
    try:
        repo = session.get(Repo, repo_id)
        assert repo is not None
        assert repo.indexed_files == 2, "La cobertura no debe reiniciarse a 0"
        assert repo.indexed_bytes == 4104
        assert repo.stats and repo.stats["by_language"].get("python") == 2
        changes = repo.last_changes or {}
        assert changes["full"] is False
        assert changes["count"] == 0
    finally:
        session.close()


def test_task_indexes_java_and_csharp(env) -> None:
    demo = Path(env["demo"])
    (demo / "Main.java").write_text(
        "package com.example;\n"
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        System.out.println(\"hi\");\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (demo / "Service.cs").write_text(
        "namespace Svc {\n"
        "    public class Service {\n"
        "        public int Add(int a, int b) { return a + b; }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    import app.db.session as db_session
    from app.db.models import Repo

    session = db_session.SessionLocal()
    try:
        repo = Repo(name="multi", source="demo", status="created")
        session.add(repo)
        session.commit()
        repo_id = repo.id
    finally:
        session.close()

    result = _run(repo_id)
    assert result["status"] == "ready"

    session = db_session.SessionLocal()
    try:
        repo = session.get(Repo, repo_id)
        assert repo is not None
        langs = (repo.stats or {})["by_language"]
        assert langs.get("java", 0) >= 1
        assert langs.get("csharp", 0) >= 1
        assert repo.indexed_files == 2
    finally:
        session.close()