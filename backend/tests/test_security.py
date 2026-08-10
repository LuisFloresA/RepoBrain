"""Tests de seguridad: validación de URLs (SSRF) y path traversal."""

from __future__ import annotations

import pytest

from app.core.security import (
    git_ssh_env,
    is_public_ip,
    resolve_within,
    validate_clone_url,
    validate_public_url,
)


def test_is_public_ip() -> None:
    assert is_public_ip("8.8.8.8")
    assert is_public_ip("142.250.72.14")
    assert not is_public_ip("10.0.0.1")
    assert not is_public_ip("172.16.0.5")
    assert not is_public_ip("192.168.1.1")
    assert not is_public_ip("169.254.169.254")  # metadata cloud
    assert not is_public_ip("127.0.0.1")
    assert not is_public_ip("::1")


def test_validate_public_url_rejects_bad_scheme() -> None:
    with pytest.raises(ValueError, match="http"):
        validate_public_url("file:///etc/passwd")


def test_validate_public_url_rejects_private_host(monkeypatch) -> None:
    def fake_getaddrinfo(host, port):
        if host == "internal.corp":
            return [(0, 0, 0, 0, ("10.0.0.5", port))]
        if host == "metadata":
            return [(0, 0, 0, 0, ("169.254.169.254", port))]
        if host == "public.example":
            return [(0, 0, 0, 0, ("93.184.216.34", port))]

    import app.core.security as security

    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="SSRF"):
        validate_public_url("https://internal.corp/repo.git")
    with pytest.raises(ValueError, match="SSRF"):
        validate_public_url("https://metadata/latest/meta-data")
    # La URL pública pasa la validación
    validate_public_url("https://public.example/repo.git")


def test_validate_public_url_resolution_failure(monkeypatch) -> None:
    import app.core.security as security

    def fake_getaddrinfo(host, port):
        raise socket.gaierror("no such host")

    import socket

    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError, match="resolver"):
        validate_public_url("https://no-such-host.example/repo.git")


def test_resolve_within_blocks_traversal(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError):
        resolve_within(root, "../../etc/passwd")
    with pytest.raises(ValueError):
        resolve_within(root, "a/../../outside")
    resolved = resolve_within(root, "sub/file.py")
    assert resolved == (root / "sub" / "file.py").resolve()


def test_validate_clone_url_ssh_normalizes_github() -> None:
    url, is_ssh = validate_clone_url("git@github.com:acme/privado.git")
    assert is_ssh is True
    assert url == "ssh://git@github.com/acme/privado.git"


def test_validate_clone_url_ssh_scheme_form() -> None:
    url, is_ssh = validate_clone_url("ssh://git@gitlab.com/team/priv.git")
    assert is_ssh is True
    assert url == "ssh://git@gitlab.com/team/priv.git"


def test_validate_clone_url_rejects_private_ssh_host(monkeypatch) -> None:
    with pytest.raises(ValueError, match="http"):
        validate_clone_url("git@172.16.0.9:intranet/repo.git")


def test_validate_clone_url_https_still_ssrf_checked(monkeypatch) -> None:
    import app.core.security as security

    def fake_getaddrinfo(host, port):
        if host == "private.example":
            return [(0, 0, 0, 0, ("10.0.0.5", port))]
        return [(0, 0, 0, 0, ("93.184.216.34", port))]

    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError, match="SSRF"):
        validate_clone_url("https://private.example/repo.git")
    url, is_ssh = validate_clone_url("https://github.com/public/repo.git")
    assert is_ssh is False
    assert url == "https://github.com/public/repo.git"


def test_validate_clone_url_rejects_scp_plain_path() -> None:
    with pytest.raises(ValueError, match="http"):
        validate_clone_url("github.com/acme/repo.git")


def test_git_ssh_env_missing_key(tmp_path) -> None:
    assert git_ssh_env(str(tmp_path / "no_existo")) is None


def test_git_ssh_env_builds_command(tmp_path) -> None:
    key = tmp_path / "deploy_key"
    key.write_text("clave-privada\n")
    env = git_ssh_env(str(key))
    assert env is not None
    cmd = env["GIT_SSH_COMMAND"]
    assert "ssh -i" in cmd
    assert "IdentitiesOnly=yes" in cmd
    assert "StrictHostKeyChecking=accept-new" in cmd
    assert "UserKnownHostsFile=/dev/null" in cmd


def test_rate_limit_exempts_health() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        for _ in range(5):
            resp = test_client.get("/health")
            assert resp.status_code == 200


def test_rate_limit_blocks_after_threshold(client, env, monkeypatch) -> None:
    from app.core.config import settings
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    monkeypatch.setattr(settings, "request_rate_limit_per_minute", 3)

    for _ in range(3):
        assert client.get("/api/repos").status_code == 200

    blocked = client.get("/api/repos")
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
