"""Tests de indexación: clonado seguro, colección de archivos y troceado."""

from __future__ import annotations

import pytest

from app.indexing.indexer import collect_files, index_directory
from app.indexing.parser import file_is_indexable
from app.indexing.repo_cloner import clone_public_repo


def test_file_is_indexable() -> None:
    assert file_is_indexable("a.py")
    assert file_is_indexable("a/b.ts")
    assert not file_is_indexable("notes.txt")
    assert not file_is_indexable(".git/config")


def test_collect_files_skips_forbidden_dirs(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("def main():\n    pass\n")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "pkg.js").write_text("x = 1;")

    files = collect_files(root)
    paths = {rel for rel, _ in files}
    assert "src/main.py" in paths
    assert ".git/config" not in paths
    assert "node_modules/pkg.js" not in paths


def test_index_directory_produces_chunks(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "auth.py").write_text(
        "import jwt\n\ndef verify_jwt(token):\n    return jwt.decode(token)\n"
    )
    chunks = index_directory(root)
    assert len(chunks) >= 1
    assert chunks[0].path == "app/auth.py"
    assert chunks[0].start_line >= 1


def test_clone_public_repo_blocks_internal(monkeypatch) -> None:
    def bad_url(_url):
        raise ValueError("La URL resuelve a una IP privada o de metadatos (SSRF bloqueado)")

    import app.indexing.repo_cloner as cloner

    monkeypatch.setattr(cloner, "validate_public_url", bad_url)
    with pytest.raises(ValueError, match="SSRF"):
        clone_public_repo("https://internal/repo.git", "abc123")


def test_clone_public_repo_uses_safe_argv(monkeypatch, env) -> None:
    import app.indexing.repo_cloner as cloner

    captured: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stderr = ""

    def fake_validate(_url):
        return None

    def fake_run(cmd, capture_output, text, timeout, check):
        captured.append(list(cmd))
        # Simula el checkout creado
        dest = cmd[-1]
        from pathlib import Path

        Path(dest).mkdir(parents=True, exist_ok=True)
        return FakeProc()

    monkeypatch.setattr(cloner, "validate_public_url", fake_validate)
    monkeypatch.setattr(cloner.subprocess, "run", fake_run)

    checkout = clone_public_repo("https://github.com/example/repo.git", "repo123")
    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[0] == "git"
    assert "--depth" in cmd
    assert "--no-hardlinks" in cmd
    assert "--single-branch" in cmd
    assert checkout.endswith("repo123")
    assert ".." not in checkout
