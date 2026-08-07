"""Parseo estático con tree-sitter.

El código indexado NUNCA se ejecuta: solo se parsea a AST. Se extraen
anclas (definiciones de funciones/clases) para guiar el troceado.
"""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Language, Parser

# Mapa de extensiones -> (lenguaje, nombres de nodos de definición)
_JS_NODES = {
    "function_declaration",
    "method_definition",
    "class_declaration",
    "generator_function_declaration",
}
_PY_NODES = {"function_definition", "class_definition", "decorated_definition"}

LANGUAGE_REGISTRY: dict[str, dict] = {
    "python": {"extensions": {".py"}, "nodes": _PY_NODES},
    "javascript": {"extensions": {".js", ".mjs", ".cjs", ".jsx"}, "nodes": _JS_NODES},
    "typescript": {"extensions": {".ts", ".tsx", ".mts", ".cts"}, "nodes": _JS_NODES},
}

SUPPORTED_EXTENSIONS: set[str] = {
    ext for lang in LANGUAGE_REGISTRY.values() for ext in lang["extensions"]
}


def language_for_path(path: str) -> str | None:
    """Devuelve el lenguaje soportado para una ruta, o None."""
    suffix = Path(path).suffix.lower()
    for lang, cfg in LANGUAGE_REGISTRY.items():
        if suffix in cfg["extensions"]:
            return lang
    return None


def _build_parser(language: str) -> Parser:
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_typescript

    if language == "python":
        lang = Language(tree_sitter_python.language())
    elif language == "typescript":
        lang = Language(tree_sitter_typescript.language_typescript())
    else:
        lang = Language(tree_sitter_javascript.language())
    return Parser(lang)


def parse_tree(source: str, language: str):
    """Parsea el source y devuelve el árbol tree-sitter (sin ejecutar nada)."""
    parser = _build_parser(language)
    return parser.parse(source.encode("utf-8"))


def extract_anchors(source: str, language: str) -> list[int]:
    """Devuelve los números de línea (1-based) de las definiciones top-level."""
    if not source.strip():
        return []

    tree = parse_tree(source, language)
    cfg = LANGUAGE_REGISTRY[language]
    nodes = cfg["nodes"]

    anchors: list[int] = []
    stack = [tree.root_node]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if node.type in nodes:
            line = node.start_point[0] + 1
            if line not in seen:
                anchors.append(line)
                seen.add(line)
        for child in node.children:
            stack.append(child)
    return sorted(anchors)


def file_is_indexable(path: str) -> bool:
    return language_for_path(path) is not None
