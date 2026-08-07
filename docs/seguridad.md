# Seguridad

RepoBrain acepta **código de terceros** (repos), así que la seguridad es parte
central del demo. Este documento mapea la matriz de amenazas a mitigaciones
reales en el código.

## Matriz de amenazas y mitigaciones

| Amenaza | Mitigación implementada |
|---|---|
| **Ejecución de código malicioso** | El código nunca se ejecuta: solo parseo estático con tree-sitter (sin `eval`, sin subprocesos del repo). Clonado con `--depth 1 --no-hardlinks` en directorio aislado. |
| **Zip bomb / repo gigante** | Límites de tamaño (`MAX_FILE_BYTES` 2 MB), nº de archivos (`MAX_REPO_FILES`) y `timeout` de clonado (`GIT_CLONE_TIMEOUT_SECONDS`). |
| **Path traversal** | `resolve_within()` (`app/core/security.py`): toda ruta se resuelve y verifica `is_relative_to` la raíz; fuera → `ValueError` (400/404). |
| **SSRF** | `validate_public_url()`: solo `http(s)`, bloquea IPs privadas, link-local, multicast y metadatos (169.254.169.254, ::1, etc.) tras resolver el host. |
| **XSS** | Visor **Monaco read-only** (sin `dangerouslySetInnerHTML`); headers `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, CSP en backend y en nginx (`frontend/nginx.conf`). |
| **Inyección LLM / alucinación** | Citas **validadas contra el checkout real** (existe el archivo y la línea); system prompt fijo; el output nunca se ejecuta. |
| **Secretos expuestos** | **Enmascarado en el visor** (`frontend/src/lib/mask.ts`): claves `sk-…`, `AKIA…`, tokens `ghp_…`, `password=` y claves privadas. Preserva el nº de líneas para no romper el resaltado. |
| **Abuso / DoS** | **Rate limiting por IP** en `/api/*` (`REQUEST_RATE_LIMIT_PER_MINUTE`, 429 + `Retry-After`), ventana deslizante en memoria. |
| **Dependencias** | Imágenes base `python:3.14-slim` (no-root, `appuser`), dependencias mínimas. CI ejecuta tests y build (recomendado: `pip-audit`/`npm audit` como paso opcional). |

## Hardening general

- **Headers de seguridad** estilo Helmet en todas las respuestas del backend
  (`SecurityHeadersMiddleware`): `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`.
- En producción **nginx** añade la CSP estricta del frontend
  (`default-src 'self'; script-src 'self'; …`) y deniega archivos ocultos
  (`location ~ /\.`).
- **DTOs Pydantic** con límites de longitud en query/body (`/search`, `/ask`).
- **Logs sin secretos**: los errores de indexación se truncan a 500 caracteres;
  no se loguean credenciales.

## Recomendaciones para producción (F3+)

- `pip-audit` + `npm audit` y generación de SBOM en CI.
- `Secret scanning` en el repo (p. ej. gitleaks) antes de cada push.
- Añadir `slowapi`/proxy con límites distribuidos si se escala a múltiples
  instancias (el rate limiter actual es por proceso).
- Subir la **CSP del demo a `report-uri`** y revisar violaciones.
