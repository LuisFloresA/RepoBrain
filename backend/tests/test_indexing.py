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
    chunks = index_directory(root).chunks
    assert len(chunks) >= 1
    assert chunks[0].path == "app/auth.py"
    assert chunks[0].start_line >= 1


def test_index_directory_with_paths_is_incremental(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "auth.py").write_text(
        "import jwt\n\ndef verify_jwt(token):\n    return jwt.decode(token)\n"
    )
    (root / "db.py").write_text(
        "from sqlalchemy import create_engine\n\ndef connect():\n    return None\n"
    )
    result = index_directory(root, paths=["app/auth.py", "botado.py"])
    paths = {c.path for c in result.chunks}
    assert "app/auth.py" in paths
    assert "db.py" not in paths
    assert result.skipped_total >= 1  # "botado.py" sin lenguaje


def test_index_directory_reports_coverage_metrics(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.js").write_text("export function run() {\n  return 1;\n}\n")
    (root / "README.txt").write_text("texto plano")
    result = index_directory(root)
    assert result.by_language.get("javascript", 0) >= 1
    assert result.indexed_bytes > 0
    assert result.skipped_total >= 1
    assert set(result.files) == {"src/main.js"}


def test_clone_public_repo_blocks_internal(monkeypatch) -> None:
    def bad_url(_url):
        raise ValueError("La URL resuelve a una IP privada o de metadatos (SSRF bloqueado)")

    import app.indexing.repo_cloner as cloner

    monkeypatch.setattr(cloner, "validate_clone_url", bad_url)
    with pytest.raises(ValueError, match="SSRF"):
        clone_public_repo("https://internal/repo.git", "abc123")


def test_clone_public_repo_uses_safe_argv(monkeypatch, env) -> None:
    import app.indexing.repo_cloner as cloner

    captured: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stderr = ""

    def fake_validate(_url):
        return _url, False

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        captured.append(list(cmd))
        # Simula el checkout creado
        dest = cmd[-1]
        from pathlib import Path

        Path(dest).mkdir(parents=True, exist_ok=True)
        return FakeProc()

    monkeypatch.setattr(cloner, "validate_clone_url", fake_validate)
    monkeypatch.setattr(cloner.subprocess, "run", fake_run)

    checkout = clone_public_repo("https://github.com/example/repo.git", "repo123")
    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[0] == "git"
    assert "--depth" in cmd
    assert "--no-hardlinks" in cmd
    assert "--single-branch" in cmd
    assert "--branch" not in cmd
    assert checkout.endswith("repo123")
    assert ".." not in checkout


def test_clone_public_repo_with_branch(monkeypatch, env) -> None:
    import app.indexing.repo_cloner as cloner

    captured: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stderr = ""

    def fake_validate(_url):
        return _url, False

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        captured.append(list(cmd))
        from pathlib import Path

        Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        return FakeProc()

    monkeypatch.setattr(cloner, "validate_clone_url", fake_validate)
    monkeypatch.setattr(cloner.subprocess, "run", fake_run)

    checkout = clone_public_repo(
        "https://github.com/example/repo.git", "repo456", branch="develop"
    )
    cmd = captured[0]
    assert "--branch" in cmd
    assert cmd[cmd.index("--branch") + 1] == "develop"
    assert checkout.endswith("repo456")


def test_clone_public_repo_ssh_requires_key(monkeypatch, env) -> None:
    import app.core.config as config

    monkeypatch.setattr(config.settings, "git_ssh_key", "")
    with pytest.raises(ValueError, match="GIT_SSH_KEY"):
        clone_public_repo("git@github.com:acme/privado.git", "repo789")


def test_clone_public_repo_ssh_sets_git_ssh_command(monkeypatch, env, tmp_path) -> None:
    from pathlib import Path

    import app.core.config as config

    key = tmp_path / "deploy_key"
    key.write_text("clave-privada-deploy\n")
    monkeypatch.setattr(config.settings, "git_ssh_key", str(key))

    import app.indexing.repo_cloner as cloner

    captured_cmds: list[list[str]] = []
    captured_envs: list[dict] = []

    class FakeProc:
        returncode = 0
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        captured_cmds.append(list(cmd))
        captured_envs.append(dict(env or {}))
        Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        return FakeProc()

    monkeypatch.setattr(cloner.subprocess, "run", fake_run)

    clone_public_repo("git@github.com:acme/privado.git", "repo555")
    cmd = captured_cmds[0]
    assert cmd[0] == "git"
    assert cmd[cmd.index("--") + 1] == "ssh://git@github.com/acme/privado.git"
    ssh_cmd = captured_envs[0]["GIT_SSH_COMMAND"]
    assert "ssh -i" in ssh_cmd
    assert "StrictHostKeyChecking=accept-new" in ssh_cmd
    assert str(key) in ssh_cmd
