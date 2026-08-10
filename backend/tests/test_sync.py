"""Tests de la sincronización incremental (git fetch/diff/reset)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.indexing.sync import sync_checkout


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return proc.stdout.strip()


def _init_remote(tmp: Path) -> Path:
    """Crea un repo remoto bare con un commit inicial."""
    seed = tmp / "seed"
    seed.mkdir()
    _git(tmp, "init", "-b", "main", str(seed))
    _git(seed, "config", "user.email", "t@t.dev")
    _git(seed, "config", "user.name", "test")
    (seed / "app.py").write_text("x = 1\n", encoding="utf-8")
    (seed / "notes.txt").write_text("nota\n", encoding="utf-8")
    _git(seed, "add", ".")
    _git(seed, "commit", "-m", "init")

    remote = tmp / "origin.git"
    _git(tmp, "clone", "--bare", str(seed), str(remote))
    return remote


def _clone(tmp: Path, remote: Path) -> Path:
    work = tmp / "work"
    _git(tmp, "clone", "--depth", "1", str(remote), str(work))
    return work


def _push_from(remote: Path, tmp: Path, payload: dict[str, str], msg: str) -> None:
    """Crea un commit en una copia de trabajo y lo empuja a `remote`."""
    pusher = tmp / "pusher"
    if pusher.exists():
        _git(pusher, "pull", "--ff-only")
    else:
        _git(tmp, "clone", "--depth", "1", str(remote), str(pusher))
    _git(pusher, "config", "user.email", "t@t.dev")
    _git(pusher, "config", "user.name", "test")
    for rel, content in payload.items():
        file_path = pusher / rel
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        _git(pusher, "add", rel)
    _git(pusher, "commit", "-m", msg)
    _git(pusher, "push", "origin", "HEAD:main")


def test_sync_missing_checkout_is_full() -> None:
    result = sync_checkout("https://example.invalid/repo.git", None, "no/existe")
    assert result.is_full is True


def test_sync_no_changes_returns_empty(tmp_path: Path) -> None:
    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    result = sync_checkout(str(remote), None, str(work))
    assert result.is_full is False
    assert result.statuses == {}
    assert result.commits == []


def test_sync_modification_reports_change_and_updates(tmp_path: Path) -> None:
    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    _push_from(remote, tmp_path, {"app.py": "x = 2\n"}, "bump")

    result = sync_checkout(str(remote), None, str(work))
    assert result.is_full is False
    assert result.statuses == {"app.py": "modificado"}
    assert result.paths == ["app.py"]
    assert result.commits and "bump" in result.commits[0]
    # El checkout local debe estar actualizado con el nuevo contenido
    assert (work / "app.py").read_text(encoding="utf-8") == "x = 2\n"


def test_sync_tracks_added_and_deleted(tmp_path: Path) -> None:
    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    _push_from(remote, tmp_path, {"new/lib.py": "y = 3\n"}, "add lib")
    _push_from(remote, tmp_path, {"notes.txt": ""}, "drop notes")  # no-op update
    # Empujar eliminación real de notes.txt
    pusher = tmp_path / "pusher"
    _git(pusher, "rm", "notes.txt")
    _git(pusher, "commit", "-m", "delete notes")
    _git(pusher, "push", "origin", "HEAD:main")

    result = sync_checkout(str(remote), None, str(work))
    assert result.is_full is False
    assert result.statuses == {"new/lib.py": "añadido", "notes.txt": "eliminado"}
    assert not (work / "notes.txt").exists()
    assert (work / "new" / "lib.py").exists()


def test_sync_full_when_too_many_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "incremental_max_changed", 1)
    remote = _init_remote(tmp_path)
    work = _clone(tmp_path, remote)
    _push_from(
        remote,
        tmp_path,
        {"a.py": "1\n", "b.py": "2\n", "c.py": "3\n"},
        "many",
    )
    result = sync_checkout(str(remote), None, str(work))
    assert result.is_full is True


def test_sync_branch_specific(tmp_path: Path) -> None:
    remote = _init_remote(tmp_path)
    seed = tmp_path / "seed"
    _git(seed, "checkout", "-b", "develop")
    (seed / "dev.py").write_text("d = 1\n", encoding="utf-8")
    _git(seed, "add", "dev.py")
    _git(seed, "commit", "-m", "dev work")
    _git(seed, "push", str(remote), "develop")

    work = tmp_path / "work"
    _git(tmp_path, "clone", "--depth", "1", "--branch", "develop", str(remote), str(work))
    assert (work / "dev.py").exists()

    result = sync_checkout(str(remote), "develop", str(work))
    assert result.is_full is False
    assert result.statuses == {}