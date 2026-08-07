"""Tests de seguridad: validación de URLs (SSRF) y path traversal."""

from __future__ import annotations

import pytest

from app.core.security import is_public_ip, resolve_within, validate_public_url


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
