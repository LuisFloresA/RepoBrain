"""Seguridad del backend: headers de protección, SSRF y path traversal.

Reglas de diseño de RepoBrain:
- Headers de seguridad en todas las respuestas (estilo Helmet).
- Solo URLs http(s) públicas; se bloquean IPs privadas, de enlace local y
  metadatos (169.254.169.254, localhost, etc.).
- Toda lectura de archivos del repo debe resolverse dentro del workspace.
"""

from __future__ import annotations

import ipaddress
import shlex
import socket
from pathlib import Path
from urllib.parse import urlparse


class SecurityHeadersMiddleware:
    """Añade cabeceras de seguridad de forma análoga a Helmet."""

    HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        # CSP estricta para el frontend; se sobreescribe en el proxy de nginx en prod.
        "Content-Security-Policy": (
            "default-src 'self'; connect-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        ),
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {k.decode("latin-1").lower() for k, _ in headers}
                caps = {k.lower(): v for k, v in self.HEADERS.items()}
                for name, value in caps.items():
                    if name not in existing:
                        headers.append((name.encode("latin-1"), value.encode("latin-1")))
            await send(message)

        await self.app(scope, receive, send_wrapper)


# Redes consideradas no públicas / no seguras para clonar
BLOCKED_NETWORKS: list[tuple[str, int]] = [
    ("0.0.0.0", 8),
    ("10.0.0.0", 8),
    ("100.64.0.0", 10),  # CGNAT
    ("127.0.0.0", 8),
    ("169.254.0.0", 16),
    ("172.16.0.0", 12),
    ("192.0.0.0", 24),
    ("192.0.2.0", 24),  # TEST-NET
    ("192.168.0.0", 16),
    ("198.18.0.0", 15),  # benchmarks
    ("198.51.100.0", 24),  # TEST-NET-2
    ("203.0.113.0", 24),  # TEST-NET-3
    ("224.0.0.0", 4),  # multicast
    ("240.0.0.0", 4),  # reservado
    ("fc00::", 7),  # ULA
    ("fe80::", 10),  # link-local
    ("ff00::", 8),  # multicast IPv6
    ("::1", 128),
    ("::", 128),
]

ALLOWED_SCHEMES = {"http", "https"}

# Hosts a los que se permite clonar vía SSH (repos privados con deploy key).
# Cualquier otro host SSH queda bloqueado: no hay SSH a redes arbitrarias.
ALLOWED_SSH_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


def _ssh_target(url: str) -> tuple[str, str] | None:
    """Devuelve `(host_part, path)` si `url` es SSH a un host permitido.

    Acepta los formatos `ssh://git@host:port/path` y `git@host:path`.
    Devuelve None para todo lo demás (no se trata de un clone SSH válido).
    """
    u = url.strip()
    if "@" not in u or (":" not in u and not u.startswith("ssh://")):
        return None

    if u.startswith("ssh://"):
        parsed = urlparse(u)
        if parsed.scheme != "ssh" or parsed.hostname not in ALLOWED_SSH_HOSTS:
            return None
        path = (parsed.path or "").lstrip("/")
        if not path:
            return None
        host_part = f"{parsed.username or 'git'}@{parsed.hostname}"
        if parsed.port is not None:
            host_part += f":{parsed.port}"
        return host_part, path

    if "://" in u:
        return None
    host_part, colon, path = u.partition(":")
    if not colon or not path:
        return None
    host = host_part.split("@")[-1].split(":")[0]
    if host not in ALLOWED_SSH_HOSTS:
        return None
    user = host_part.split("@")[0] if "@" in host_part else "git"
    return f"{user}@{host}", path


def validate_clone_url(url: str) -> tuple[str, bool]:
    """Valida una URL de repositorio para clonar y devuelve `(url, es_ssh)`.

    - http(s): comprobación SSRF habitual (IPs privadas/metadatos bloqueadas).
    - SSH a github.com/gitlab.com/bitbucket.org: permite repos privados con
      deploy key (GIT_SSH_KEY). Normaliza el formato scp-like a `ssh://`.
    """
    target = _ssh_target(url)
    if target is not None:
        host_part, path = target
        return f"ssh://{host_part}/{path}", True
    validate_public_url(url)
    return url, False


def git_ssh_env(key_path: str) -> dict[str, str] | None:
    """Construye `GIT_SSH_COMMAND` para usar `key_path` como deploy key.

    Devuelve None si la clave no existe o no es un archivo (entonces no se
    fuerza SSH y la operación git fallará con su mensaje natural).
    `accept-new` evita requerir known_hosts previos sin desactivar la verificación.
    """
    path = Path(key_path).expanduser()
    if not path.is_file():
        return None
    quoted = shlex.quote(str(path.resolve()))
    return {
        "GIT_SSH_COMMAND": (
            f"ssh -i {quoted} -o IdentitiesOnly=yes "
            "-o StrictHostKeyChecking=accept-new "
            "-o UserKnownHostsFile=/dev/null"
        )
    }


def is_public_ip(ip: str) -> bool:
    """Devuelve True si la IP es pública (no está en redes bloqueadas)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if not any(
        addr in ipaddress.ip_network(f"{net}/{prefix}") for net, prefix in BLOCKED_NETWORKS
    ):
        return True
    return False


def validate_public_url(url: str) -> None:
    """Valida que `url` sea http(s) pública. Lanza ValueError en caso contrario."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError("Solo se permiten URLs http/https")
    if not parsed.hostname:
        raise ValueError("URL sin host válido")

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except socket.gaierror as exc:
        raise ValueError(f"No se pudo resolver el host: {parsed.hostname}") from exc

    resolved = {info[4][0] for info in infos}
    if not any(is_public_ip(ip) for ip in resolved):
        raise ValueError("La URL resuelve a una IP privada o de metadatos (SSRF bloqueado)")


def resolve_within(root: str | Path, rel_path: str) -> Path:
    """Resuelve `rel_path` dentro de `root`, bloqueando path traversal.

    Lanza ValueError si la ruta resultante queda fuera del root.
    """
    base = Path(root).resolve()
    target = (base / rel_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Ruta fuera del workspace: {rel_path}")
    return target
