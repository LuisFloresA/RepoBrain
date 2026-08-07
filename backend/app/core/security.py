"""Middleware de seguridad del backend (headers de protección)."""

from __future__ import annotations


class SecurityHeadersMiddleware:
    """Añade cabeceras de seguridad de forma análoga a Helmet.

    Estas cabeceras se complementarán en F3 con CSP dinámica y rate
    limiting. Aquí se fijan las invariantes base (hardening-first).
    """

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