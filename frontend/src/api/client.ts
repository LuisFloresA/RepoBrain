import type {
  Architecture,
  AskResponse,
  CodeFile,
  HealthStatus,
  Repo,
  RepoBranchesResponse,
  SearchResponse,
} from "./types";

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 25000,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const resp = await fetch(path, {
      ...init,
      signal: init?.signal ?? controller.signal,
    });
    clearTimeout(timeoutId);
    if (!resp.ok) {
      let detail = `Error ${resp.status}`;
      try {
        const body = (await resp.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        /* respuesta no JSON */
      }
      throw new Error(detail);
    }
    return (await resp.json()) as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Tiempo de espera agotado al comunicarse con el servidor. Intenta de nuevo.");
    }
    throw err;
  }
}

export async function fetchHealth(endpoint = "/health"): Promise<HealthStatus> {
  return request<HealthStatus>(endpoint);
}

export async function getRepos(): Promise<Repo[]> {
  return request<Repo[]>("/api/repos");
}

export async function cleanupRepos(): Promise<void> {
  await request<{ message: string }>("/api/repos", { method: "DELETE" });
}

export async function deleteRepo(id: string, keepalive = false): Promise<void> {
  await request<{ message: string }>(`/api/repos/${id}`, {
    method: "DELETE",
    keepalive,
  });
}

export async function createRepo(
  payload: { url?: string; name?: string; source: string; branch?: string | null },
): Promise<Repo> {
  return request<Repo>("/api/repos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getRepoStatus(id: string): Promise<Repo> {
  return request<Repo>(`/api/repos/${id}/status`);
}

export async function searchRepo(
  id: string,
  q: string,
  topK = 10,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, top_k: String(topK) });
  return request<SearchResponse>(`/api/repos/${id}/search?${params}`);
}

export async function getFile(id: string, path: string): Promise<CodeFile> {
  return request<CodeFile>(
    `/api/repos/${id}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
  );
}

export async function askQuestion(
  id: string,
  question: string,
  topK = 5,
): Promise<AskResponse> {
  return request<AskResponse>(
    `/api/repos/${id}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK }),
    },
    35000,
  );
}

export async function getArchitecture(id: string): Promise<Architecture> {
  return request<Architecture>(`/api/repos/${id}/architecture`);
}

export async function getRepoBranches(url: string): Promise<RepoBranchesResponse> {
  const params = new URLSearchParams({ url });
  return request<RepoBranchesResponse>(`/api/repos/branches?${params}`);
}
