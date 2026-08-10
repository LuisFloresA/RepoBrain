"""Generación del mapa de arquitectura (Mermaid + Markdown) de un repo.

Recorre los fuentes del checkout y extrae con tree-sitter los símbolos
(clases, namespaces, funciones/métodos), para construir un grafo
archivo -> contenedor -> símbolo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.db.models import Repo
from app.indexing.indexer import _walk, read_source
from app.indexing.parser import extract_symbols, file_is_indexable, language_for_path

_CONTAINER_KINDS = {
    "class",
    "struct",
    "record",
    "interface",
    "enum",
    "namespace",
}


def _checkout_root(repo: Repo) -> Path:
    if repo.source == "url":
        base = Path(repo.checkout_dir or "")
    elif repo.source == "demo":
        base = Path(settings.demo_data_dir)
    elif repo.source == "upload":
        base = Path(settings.workspace_root) / "uploads" / repo.id
    else:
        raise ValueError(f"Fuente desconocida: {repo.source}")
    if not base.is_dir():
        raise FileNotFoundError("Checkout no disponible")
    return base.resolve()


def build_architecture(repo: Repo) -> dict:
    """Devuelve {nodes, edges, mermaid, markdown} listos para serializar."""
    root = _checkout_root(repo)
    nodes: list[dict] = []
    edges: list[dict] = []
    by_language: dict[str, int] = {}

    for abs_path in _walk(root):
        rel = str(abs_path.relative_to(root)).replace("\\", "/")
        if not file_is_indexable(rel):
            continue
        try:
            source = read_source(abs_path)
        except (OSError, ValueError):
            continue

        lang = language_for_path(rel)
        symbols = extract_symbols(source, lang or "python")
        by_language[lang or "?"] = by_language.get(lang or "?", 0) + len(symbols)

        file_id = f"f{len(nodes)}"
        nodes.append(
            {"id": file_id, "label": rel, "kind": "file", "path": rel, "line": 1}
        )

        spans = [
            {"kind": s.kind, "name": s.name, "start": s.start_line, "end": s.end_line}
            for s in symbols
        ]
        spans.sort(key=lambda s: (s["start"], s["end"]))

        opened: list[dict] = []  # contenedores aún abiertos
        container_ids: dict[tuple[str, int], str] = {}
        for span in spans:
            nid = f"n{len(nodes)}"
            nodes.append(
                {
                    "id": nid,
                    "label": span["name"],
                    "kind": span["kind"],
                    "path": rel,
                    "line": span["start"],
                }
            )
            container_ids[(span["kind"], span["start"])] = nid

            if span["kind"] in _CONTAINER_KINDS:
                opened = [c for c in opened if c["end"] >= span["start"]]
                opened.append(span)
                edges.append({"source": file_id, "target": nid})
            else:  # función / método
                container = opened[-1] if opened else None
                parent = (
                    container_ids.get((container["kind"], container["start"]))
                    if container
                    else None
                )
                edges.append({"source": parent or file_id, "target": nid})

    mermaid = _render_mermaid(nodes, edges)
    markdown = _render_markdown(repo, nodes, edges, by_language)
    return {"nodes": nodes, "edges": edges, "mermaid": mermaid, "markdown": markdown}


def _clean_label(label: str) -> str:
    return label.replace('"', "'").replace("[", "(").replace("]", ")")


def _shape(kind: str) -> str:
    if kind == "file":
        return "(["
    if kind in _CONTAINER_KINDS:
        return "["
    return "("


def _render_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["graph TD"]
    for n in nodes:
        lines.append(f'    {n["id"]}{_shape(n["kind"])}["{_clean_label(n["label"])}"]')
    for e in edges:
        lines.append(f"    {e['source']} --> {e['target']}")
    return "\n".join(lines)


def _render_markdown(
    repo: Repo, nodes: list[dict], edges: list[dict], by_language: dict[str, int]
) -> str:
    files = [n for n in nodes if n["kind"] == "file"]
    containers = [n for n in nodes if n["kind"] != "file" and n["kind"] != "function"]
    funcs = [n for n in nodes if n["kind"] == "function"]
    lang_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_language.items()))

    lines = [
        f"# Mapa de arquitectura — {repo.name}",
        "",
        f"_Generado el {datetime.now(UTC):%Y-%m-%d %H:%M} UTC a partir de "
        f"{len(files)} archivos indexados._",
        "",
        "## Resumen",
        "",
        "| Métrica | Valor |",
        "| --- | --- |",
        f"| Archivos | {len(files)} |",
        f"| Clases / contenedores | {len(containers)} |",
        f"| Funciones / métodos | {len(funcs)} |",
        f"| Símbolos por lenguaje | {lang_summary or '-'} |",
        "",
        "## Grafo",
        "",
        "```mermaid",
        _render_mermaid(nodes, edges),
        "```",
        "",
        "## Desglose por archivo",
        "",
    ]

    per_file: dict[str, list[dict]] = {}
    for e in edges:
        src = next((n for n in nodes if n["id"] == e["source"]), None)
        tgt = next((n for n in nodes if n["id"] == e["target"]), None)
        if not src or not tgt:
            continue
        if src["kind"] == "file":
            per_file.setdefault(src["label"], []).append(tgt)

    for path in sorted(per_file):
        lines.append(f"### `{path}`")
        for child in per_file[path]:
            if child["kind"] == "function":
                lines.append(f"- `{child['label']}` — línea {child['line']}")
            else:
                lines.append(f"- **{child['kind']}** `{child['label']}` — línea {child['line']}")
        lines.append("")

    return "\n".join(lines)