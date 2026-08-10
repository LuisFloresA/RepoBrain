"""Parseo estático con tree-sitter.

El código indexado NUNCA se ejecuta: solo se parsea a AST. Se extraen
anclas (definiciones de funciones/clases) para guiar el troceado.
"""

from __future__ import annotations

from dataclasses import dataclass
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
_JAVA_NODES = {
    "method_declaration",
    "constructor_declaration",
    "class_declaration",
    "interface_declaration",
    "record_declaration",
    "enum_declaration",
}
_CSHARP_NODES = {
    "method_declaration",
    "constructor_declaration",
    "class_declaration",
    "interface_declaration",
    "record_declaration",
    "struct_declaration",
    "enum_declaration",
    "namespace_declaration",
}

LANGUAGE_REGISTRY: dict[str, dict] = {
    "python": {"extensions": {".py"}, "nodes": _PY_NODES},
    "javascript": {"extensions": {".js", ".mjs", ".cjs", ".jsx"}, "nodes": _JS_NODES},
    "typescript": {"extensions": {".ts", ".tsx", ".mts", ".cts"}, "nodes": _JS_NODES},
    "java": {"extensions": {".java"}, "nodes": _JAVA_NODES},
    "csharp": {"extensions": {".cs"}, "nodes": _CSHARP_NODES},
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
    import tree_sitter_c_sharp
    import tree_sitter_java
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_typescript

    if language == "python":
        lang = Language(tree_sitter_python.language())
    elif language == "typescript":
        lang = Language(tree_sitter_typescript.language_typescript())
    elif language == "java":
        lang = Language(tree_sitter_java.language())
    elif language == "csharp":
        lang = Language(tree_sitter_c_sharp.language())
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


_KIND_BY_NODE = {
    # (nodo -> kind de símbolo)
    "class_definition": "class",
    "class_declaration": "class",
    "record_declaration": "record",
    "interface_declaration": "interface",
    "struct_declaration": "struct",
    "enum_declaration": "enum",
    "namespace_declaration": "namespace",
    "function_definition": "function",
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "method_definition": "function",
    "method_declaration": "function",
    "constructor_declaration": "function",
}


@dataclass
class Symbol:
    kind: str
    name: str
    start_line: int
    end_line: int


def _symbol_name(node) -> str:
    for child in node.children:
        if child.type == "identifier":
            return child.text.decode("utf-8", "replace")
    name = node.child_by_field_name("name")
    if name is not None:
        return name.text.decode("utf-8", "replace")
    return node.type


def extract_symbols(source: str, language: str) -> list[Symbol]:
    """Devuelve clases/namespaces/funciones (incl. métodos) con su rango.

    No ejecuta nada: solo recorre el AST. No desciende por cuerpos de
    función (evita anidamientos/lambdas internas).
    """
    if not source.strip():
        return []

    tree = parse_tree(source, language)
    symbols: list[Symbol] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        kind = _KIND_BY_NODE.get(node.type)
        if kind:
            symbols.append(
                Symbol(
                    kind=kind,
                    name=_symbol_name(node),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
            )
            if kind == "function":
                continue  # no bajar por el cuerpo de una función
        for child in node.children:
            stack.append(child)
    return symbols


def file_is_indexable(path: str) -> bool:
    return language_for_path(path) is not None
