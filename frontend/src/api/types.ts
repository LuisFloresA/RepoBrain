export type RepoStatus = "created" | "indexing" | "ready" | "failed";

export interface Repo {
  id: string;
  name: string;
  url: string | null;
  source: string;
  status: RepoStatus;
  progress: number;
  message: string | null;
  file_count: number;
  chunk_count: number;
  created_at: string;
}

export interface SearchResult {
  chunk_id: string;
  path: string;
  start_line: number;
  end_line: number;
  snippet: string;
  score: number;
  bm25_score: number;
  semantic_score: number;
}

export interface SearchResponse {
  query: string;
  repo_id: string;
  top_k: number;
  results: SearchResult[];
}

export interface CodeFile {
  path: string;
  language: string | null;
  content: string;
  line_count: number;
}

export interface Citation {
  path: string;
  start_line: number;
  end_line: number;
}

export interface AskResponse {
  question: string;
  answer: string;
  citations: Citation[];
  llm: string;
  source: "mock" | "openai-compatible" | "none";
}

export interface HealthStatus {
  status: "ok" | "degraded";
  service: string;
  environment: string;
  dependencies?: Record<string, string>;
}
