"""DTOs Pydantic de la API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepoCreate(BaseModel):
    url: HttpUrl | None = None
    name: str | None = Field(default=None, max_length=255)
    source: str = Field(default="url", pattern="^(url|demo|upload)$")


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str | None = None
    source: str
    status: str
    progress: float
    message: str | None = None
    file_count: int
    chunk_count: int
    created_at: datetime


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


class FileOut(BaseModel):
    path: str
    language: str | None = None
    content: str
    line_count: int


class MessageOut(BaseModel):
    message: str
