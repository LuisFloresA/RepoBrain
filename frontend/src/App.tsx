import { useCallback, useEffect, useRef, useState } from "react";
import {
  cleanupRepos,
  createRepo,
  deleteRepo,
  getFile,
  getRepoStatus,
  searchRepo,
} from "./api/client";
import type { CodeFile, Repo, SearchResult } from "./api/types";
import { AskPanel } from "./components/AskPanel";
import { CodeViewer } from "./components/CodeViewer";
import { MetricsPanel } from "./components/MetricsPanel";
import { ProgressModal } from "./components/ProgressModal";
import { RepoSetup } from "./components/RepoSetup";
import { ResultsList } from "./components/ResultsList";
import { SearchBox } from "./components/SearchBox";

const DEMO_NAME = "Demo · login-api (JWT)";

export function App() {
  const [repo, setRepo] = useState<Repo | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedFile, setSelectedFile] = useState<CodeFile | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [setupBusy, setSetupBusy] = useState(false);
  const [backendStatus, setBackendStatus] = useState<string>("…");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionRepoRef = useRef<string | null>(null);

  useEffect(() => {
    void cleanupRepos().catch(() => {
      /* la limpieza de sesiones previas es best-effort */
    });
    void fetch("/health")
      .then((r) => r.json())
      .then((h: { status: string }) => setBackendStatus(h.status))
      .catch(() => setBackendStatus("offline"));
  }, []);

  // Sesión efímera: al salir de la página se borra el repo indexado.
  useEffect(() => {
    const cleanup = () => {
      const id = sessionRepoRef.current;
      if (id) {
        void deleteRepo(id, true).catch(() => {
          /* el cleanup del próximo arranque cubre lo que quede */
        });
      }
    };
    window.addEventListener("beforeunload", cleanup);
    window.addEventListener("pagehide", cleanup);
    return () => {
      window.removeEventListener("beforeunload", cleanup);
      window.removeEventListener("pagehide", cleanup);
    };
  }, []);

  // Polling del estado de indexación
  const repoId = repo?.id;
  const repoStatus = repo?.status;
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (!repoId || repoStatus === "ready" || repoStatus === "failed") {
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const fresh = await getRepoStatus(repoId);
        setRepo((prev) => (prev && prev.id === fresh.id ? fresh : prev));
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
      if (!repoId) return;
      setError(null);
      setLoading(true);
      try {
        const res = await searchRepo(repoId, q);
        setResults(res.results);
        setSelectedFile(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [repoId],
  );

  const handleIndex = async (url: string, branch: string) => {
    setError(null);
    setSetupBusy(true);
    try {
      const created = await createRepo({
        url,
        source: "url",
        branch: branch || null,
      });
      sessionRepoRef.current = created.id;
      setRepo(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSetupBusy(false);
    }
  };

  const handleDemo = async () => {
    setError(null);
    setSetupBusy(true);
    try {
      const created = await createRepo({ source: "demo", name: DEMO_NAME });
      sessionRepoRef.current = created.id;
      setRepo(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSetupBusy(false);
    }
  };

  const handleModalClose = () => {
    const id = sessionRepoRef.current;
    sessionRepoRef.current = null;
    setRepo(null);
    setResults([]);
    setSelectedFile(null);
    if (id) {
      void deleteRepo(id).catch(() => {
        /* best-effort */
      });
    }
  };

  const handleSelectResult = async (result: SearchResult) => {
    if (!repoId) return;
    setHighlightLine(result.start_line);
    try {
      const file = await getFile(repoId, result.path);
      setSelectedFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const openFileAt = async (path: string, line: number) => {
    if (!repoId) return;
    setHighlightLine(line);
    try {
      const file = await getFile(repoId, path);
      setSelectedFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const repoReady = repo?.status === "ready";
  const showModal =
    repo !== null && repo.status !== "ready";

  return (
    <div className="layout">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-brand">
            <h1>
              Repo<span>Brain</span>
            </h1>
            <p className="tagline">
              Búsqueda semántica y Q&amp;A sobre código fuente
            </p>
          </div>
          <div className="topbar-status" aria-live="polite">
            (API: <span className={`backend-pill ${backendStatus}`}>{backendStatus}</span>)
          </div>
        </div>
      </header>

      <main className="content">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {!repo ? (
          <RepoSetup
            onIndex={(url, branch) => void handleIndex(url, branch)}
            onDemo={() => void handleDemo()}
            disabled={setupBusy}
          />
        ) : (
          <>
            <section className="search-section" aria-label="Buscar en el código">
              <div className="section-heading">
                <span className="section-num" aria-hidden="true">
                  1
                </span>
                <div>
                  <h2 className="section-title">Buscar en el código</h2>
                  <p className="section-subtitle">
                    Encuentra los fragmentos de código relevantes para tu
                    pregunta.
                  </p>
                </div>
              </div>
              <SearchBox
                query={query}
                onQueryChange={setQuery}
                onSubmit={() => void runSearch(query.trim())}
                disabled={!repoReady}
                loading={loading}
              />
            </section>

            {repoReady && <MetricsPanel repo={repo} />}

            <AskPanel
              key={repoId ?? "no-repo"}
              repoId={repoId ?? ""}
              onOpenFile={(path, line) => void openFileAt(path, line)}
              disabled={!repoReady}
            />

            <div className="panels">
              <section aria-label="Resultados">
                {loading ? (
                  <div className="search-loading-panel" role="status" aria-live="polite">
                    <div className="spinner-ring" aria-hidden="true" />
                    <div className="search-loading-text">
                      <strong>Buscando en el repositorio…</strong>
                      <span>Analizando fragmentos semánticos y léxicos en el código.</span>
                    </div>
                  </div>
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
          </>
        )}
      </main>

      {showModal && repo && (
        <ProgressModal repo={repo} onClose={handleModalClose} />
      )}
    </div>
  );
}
