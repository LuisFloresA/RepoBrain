import { useCallback, useEffect, useRef, useState } from "react";
import {
  createRepo,
  getFile,
  getRepoStatus,
  getRepos,
  searchRepo,
} from "./api/client";
import type { CodeFile, Repo, SearchResult } from "./api/types";
import { CodeViewer } from "./components/CodeViewer";
import { ProgressBar } from "./components/ProgressBar";
import { RepoPicker } from "./components/RepoPicker";
import { ResultsList } from "./components/ResultsList";
import { SearchBox } from "./components/SearchBox";

const DEMO_QUERY = "¿dónde se valida el JWT?";

export function App() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedFile, setSelectedFile] = useState<CodeFile | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addUrl, setAddUrl] = useState("");
  const [backendStatus, setBackendStatus] = useState<string>("…");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const activeRepo = repos.find((r) => r.id === activeRepoId) ?? null;

  const loadRepos = useCallback(async () => {
    try {
      const list = await getRepos();
      setRepos(list);
      const demo = list.find((r) => r.source === "demo") ?? null;
      const ready = list.find((r) => r.status === "ready") ?? null;
      if (!activeRepoId) {
        setActiveRepoId((demo ?? ready ?? list[0])?.id ?? null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [activeRepoId]);

  useEffect(() => {
    void loadRepos();
  }, [loadRepos]);

  useEffect(() => {
    void fetch("/health")
      .then((r) => r.json())
      .then((h: { status: string }) => setBackendStatus(h.status))
      .catch(() => setBackendStatus("offline"));
  }, []);

  // Polling del estado de indexación
  const repoId = activeRepo?.id;
  const repoStatus = activeRepo?.status;
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!repoId || repoStatus !== "indexing") {
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const fresh = await getRepoStatus(repoId);
        setRepos((prev) =>
          prev.map((r) => (r.id === fresh.id ? fresh : r)),
        );
      } catch {
        /* el poll reintenta */
      }
    }, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [repoId, repoStatus]);

  const runSearch = useCallback(
    async (q: string) => {
      if (!activeRepoId) return;
      setError(null);
      setLoading(true);
      try {
        const res = await searchRepo(activeRepoId, q);
        setResults(res.results);
        setSelectedFile(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [activeRepoId],
  );

  // Auto-búsqueda cuando el repo de demo queda listo
  useEffect(() => {
    if (activeRepo?.status === "ready" && pendingQuery) {
      void runSearch(pendingQuery);
      setPendingQuery(null);
    }
  }, [activeRepo?.status, pendingQuery, runSearch]);

  const handleSubmit = () => {
    if (!query.trim()) return;
    setPendingQuery(null);
    void runSearch(query.trim());
  };

  const handleDemo = async () => {
    setQuery(DEMO_QUERY);
    if (activeRepo && activeRepo.status === "ready") {
      await runSearch(DEMO_QUERY);
      return;
    }
    // Crea el repo demo si no está listo, y dispara la búsqueda cuando termine
    setPendingQuery(DEMO_QUERY);
    if (!activeRepoId) {
      try {
        const demo = await createRepo({ source: "demo", name: "Demo · login-api" });
        setRepos((prev) => [demo, ...prev]);
        setActiveRepoId(demo.id);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }
  };

  const handleSelectResult = async (result: SearchResult) => {
    if (!activeRepoId) return;
    setHighlightLine(result.start_line);
    try {
      const file = await getFile(activeRepoId, result.path);
      setSelectedFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleAddRepo = async () => {
    if (!addUrl.trim()) return;
    setError(null);
    try {
      const repo = await createRepo({
        url: addUrl.trim(),
        source: "url",
      });
      setRepos((prev) => [repo, ...prev]);
      setActiveRepoId(repo.id);
      setAddUrl("");
      setShowAddForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const selectRepo = (id: string) => {
    setActiveRepoId(id);
    setResults([]);
    setSelectedFile(null);
    setPendingQuery(null);
  };

  return (
    <div className="layout">
      <header className="topbar">
        <h1>
          Repo<span>Brain</span>
        </h1>
        <p className="tagline">
          Búsqueda semántica y Q&amp;A sobre código fuente · backend:{" "}
          <span className={`backend-pill ${backendStatus}`}>{backendStatus}</span>
        </p>
      </header>

      <RepoPicker
        repos={repos}
        activeId={activeRepoId}
        onSelect={selectRepo}
        onAdd={() => setShowAddForm((v) => !v)}
      />

      <main className="content">
        {showAddForm && (
          <div className="add-form">
            <input
              type="url"
              placeholder="https://github.com/usuario/repo"
              value={addUrl}
              onChange={(e) => setAddUrl(e.target.value)}
            />
            <button type="button" onClick={handleAddRepo}>
              Indexar
            </button>
          </div>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <SearchBox
          query={query}
          onQueryChange={setQuery}
          onSubmit={handleSubmit}
          onDemo={handleDemo}
          disabled={!activeRepo || activeRepo.status !== "ready"}
        />

        {activeRepo && <ProgressBar {...activeRepo} />}

        <div className="panels">
          <section aria-label="Resultados">
            {loading ? (
              <p className="loading">Buscando…</p>
            ) : (
              <ResultsList
                results={results}
                query={query}
                onSelect={(r) => void handleSelectResult(r)}
              />
            )}
          </section>

          <section aria-label="Visor de código">
            {selectedFile ? (
              <CodeViewer
                file={selectedFile}
                highlightLine={highlightLine}
              />
            ) : (
              <div className="empty-viewer">
                Haz clic en un resultado para ver el código con la línea
                resaltada.
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
