"""DTOs Pydantic de la API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepoCreate(BaseModel):
    url: HttpUrl | None = None
    name: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=255)
    source: str = Field(default="url", pattern="^(url|demo|upload)$")


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str | None = None
    branch: str | None = None
    source: str
    status: str
    progress: float
    message: str | None = None
    file_count: int
    chunk_count: int
    source_rev: str | None = None
    indexed_files: int | None = None
    skipped_files: int | None = None
    indexed_bytes: int | None = None
    last_indexed_at: datetime | None = None
    stats: dict[str, Any] | None = None
    last_changes: dict[str, Any] | None = None
    created_at: datetime


class ArchitectureNode(BaseModel):
    id: str
    label: str
    kind: str  # file | class | function
    path: str
    line: int


class ArchitectureEdge(BaseModel):
    source: str
    target: str


class ArchitectureOut(BaseModel):
    repo_id: str
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    mermaid: str
    markdown: str


class SearchResult(BaseModel):
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    bm25_score: float = 0.0
    semantic_score: float = 0.0


class SearchResponse(BaseModel):
    query: str
    repo_id: str
    top_k: int
    results: list[SearchResult]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    llm: str
    source: str  # mock | openai-compatible | none


class FileOut(BaseModel):
    path: str
    language: str | None = None
    content: str
    line_count: int


class MessageOut(BaseModel):
    message: str
