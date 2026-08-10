export type RepoStatus = "created" | "indexing" | "ready" | "failed";

export interface RepoStats {
  by_language?: Record<string, number>;
  skipped_reasons?: Record<string, number>;
  indexed_bytes?: number;
}

export interface ChangeFile {
  path: string;
  status: string;
}

export interface RepoLastChanges {
  full: boolean;
  count: number | null;
  files: ChangeFile[] | null;
  commits: string[] | null;
}

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
  branch?: string | null;
  source_rev?: string | null;
  indexed_files?: number | null;
  skipped_files?: number | null;
  indexed_bytes?: number | null;
  last_indexed_at?: string | null;
  stats?: RepoStats | null;
  last_changes?: RepoLastChanges | null;
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

export interface ArchitectureNode {
  id: string;
  label: string;
  kind: "file" | "class" | "function" | string;
  path: string;
  line: number;
}

export interface ArchitectureEdge {
  source: string;
  target: string;
}

export interface Architecture {
  repo_id: string;
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  mermaid: string;
  markdown: string;
}
