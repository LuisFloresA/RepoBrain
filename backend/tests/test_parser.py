"""Tests del parser tree-sitter y del troceado."""

from __future__ import annotations

from app.indexing.chunker import Chunk, chunk_source, estimate_tokens
from app.indexing.parser import extract_anchors, language_for_path, parse_tree

PY_SOURCE = """\
import jwt


def verify_jwt(token):
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload


class User:
    def soft_delete(self):
        self.deleted = True
"""

JS_SOURCE = """\
function handleLogin(req, res) {
  const token = signJwt(req.body.email);
  res.json({ token });
}

class Server {
  start(port) {
    this.listen(port);
  }
}
"""


def test_language_for_path() -> None:
    assert language_for_path("app/auth.py") == "python"
    assert language_for_path("web/api.js") == "javascript"
    assert language_for_path("web/api.tsx") == "typescript"
    assert language_for_path("README.md") is None


def test_parse_tree_python_creates_ast() -> None:
    tree = parse_tree(PY_SOURCE, "python")
    assert tree.root_node is not None
    assert tree.root_node.type == "module"


def test_extract_anchors_python() -> None:
    anchors = extract_anchors(PY_SOURCE, "python")
    assert 4 in anchors  # def verify_jwt
    assert 9 in anchors  # class User
    assert 10 in anchors  # def soft_delete


def test_extract_anchors_javascript() -> None:
    anchors = extract_anchors(JS_SOURCE, "javascript")
    assert 1 in anchors  # function handleLogin
    assert 6 in anchors  # class Server
    assert 7 in anchors  # start(port)


def test_parse_is_static_and_safe() -> None:
    # El parseo nunca ejecuta código: una fuente con side effects es inofensiva
    dangerous = 'import os\nos.system("echo pwned")\n'
    tree = parse_tree(dangerous, "python")
    assert tree.root_node is not None


def test_chunk_source_splits_by_lines() -> None:
    source = "\n".join(f"line {i} = {i}" for i in range(200))
    chunks = chunk_source("big.py", source, use_anchors=False)
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)
    first = chunks[0]
    assert first.path == "big.py"
    assert first.start_line == 1


def test_chunk_source_respects_max_tokens() -> None:
    long_line = "x = " + " ".join("word" for _ in range(5000))
    chunks = chunk_source("big.py", long_line, use_anchors=False, max_tokens=512)
    assert all(c.token_count <= 512 for c in chunks)


def test_chunk_source_aligned_to_anchors() -> None:
    chunks = chunk_source("auth.py", PY_SOURCE, max_tokens=512)
    starts = {c.start_line for c in chunks}
    assert 4 in starts  # verify_jwt empieza un chunk
    assert 10 in starts  # soft_delete empieza un chunk


def test_chunk_source_keeps_header_before_first_anchor() -> None:
    source = (
        "import jwt\n\n"
        "SECRET_KEY = 'x'\n\n"
        "def verify_jwt(token):\n"
        "    return jwt.decode(token)\n"
    )
    chunks = chunk_source("auth.py", source, max_tokens=512)
    # El prefijo (imports/config) antes del primer anchor debe estar indexado
    assert any(c.start_line == 1 and "import jwt" in c.text for c in chunks)
    assert any(c.start_line == 5 and "verify_jwt" in c.text for c in chunks)


def test_estimate_tokens() -> None:
    assert estimate_tokens("a b c") >= 3
    assert estimate_tokens("") == 1


def test_chunk_source_empty() -> None:
    assert chunk_source("x.py", "") == []
