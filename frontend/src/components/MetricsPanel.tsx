import { useState } from "react";
import { getArchitecture } from "../api/client";
import type { Architecture, Repo } from "../api/types";

interface MetricsPanelProps {
  repo: Repo;
}

function formatBytes(n: number | null | undefined): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function shortRev(rev: string | null | undefined): string | null {
  return rev ? rev.slice(0, 8) : null;
}

export function MetricsPanel({ repo }: MetricsPanelProps) {
  const [arch, setArch] = useState<Architecture | null>(null);
  const [archBusy, setArchBusy] = useState(false);
  const [archError, setArchError] = useState<string | null>(null);

  const stats = repo.stats;
  const changes = repo.last_changes;
  const byLang = stats?.by_language ?? {};
  const langTotal = Object.values(byLang).reduce((a, b) => a + b, 0);

  const exportMap = async () => {
    if (repo.status !== "ready") return;
    setArchBusy(true);
    setArchError(null);
    try {
      const data = await getArchitecture(repo.id);
      setArch(data);
      const blob = new Blob([data.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `arquitectura-${repo.name.replace(/[^\w-]/g, "_").toLowerCase()}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setArchError(e instanceof Error ? e.message : String(e));
    } finally {
      setArchBusy(false);
    }
  };

  return (
    <section className="metrics" aria-label="Métricas del repositorio">
      <div className="metrics-grid">
        <div className="metric">
          <span className="metric-value">{repo.indexed_files ?? repo.file_count}</span>
          <span className="metric-label">archivos indexados</span>
        </div>
        <div className="metric">
          <span className="metric-value">{repo.chunk_count}</span>
          <span className="metric-label">chunks</span>
        </div>
        <div className="metric">
          <span className="metric-value">{formatBytes(repo.indexed_bytes)}</span>
          <span className="metric-label">bytes útiles</span>
        </div>
        <div className="metric">
          <span className="metric-value">{repo.skipped_files ?? 0}</span>
          <span className="metric-label">omitidos</span>
        </div>
      </div>

      <div className="metrics-row">
        <span>
          Rama: <strong>{repo.branch || "default"}</strong>
          {shortRev(repo.source_rev) && (
            <>
              {" · "}rev{" "}
              <code className="rev">{shortRev(repo.source_rev)}</code>
            </>
          )}
        </span>
        {repo.last_indexed_at && (
          <span>
            Último índice:{" "}
            <strong>{new Date(repo.last_indexed_at).toLocaleString()}</strong>
          </span>
        )}
      </div>

      {langTotal > 0 && (
        <div className="metrics-langs">
          {Object.entries(byLang)
            .sort((a, b) => b[1] - a[1])
            .map(([lang, count]) => (
              <span key={lang} className="lang-chip">
                <code>{lang}</code> {count}
              </span>
            ))}
        </div>
      )}

      {changes && (
        <div className="metrics-changes">
          {changes.full ? (
            <p>Última indexación: reindexado completo.</p>
          ) : (
            <>
              <p>
                Última actualización: <strong>{changes.count ?? 0}</strong> archivo
                {(changes.count ?? 0) === 1 ? "" : "s"} cambiado
                {(changes.count ?? 0) === 1 ? "" : "s"}.
              </p>
              {changes.files && changes.files.length > 0 && (
                <ul className="change-list">
                  {changes.files.slice(0, 12).map((f) => (
                    <li key={f.path} className={`change-${f.status.split(" ")[0]}`}>
                      <code>{f.path}</code> <em>{f.status}</em>
                    </li>
                  ))}
                  {(changes.files.length ?? 0) > 12 && <li>… y más</li>}
                </ul>
              )}
              {changes.commits && changes.commits.length > 0 && (
                <p className="commits">
                  {changes.commits.slice(0, 3).join(" · ")}
                </p>
              )}
            </>
          )}
        </div>
      )}

      <div className="metrics-actions">
        <button
          type="button"
          onClick={() => void exportMap()}
          disabled={repo.status !== "ready" || archBusy}
        >
          {archBusy ? "Generando…" : "Exportar mapa de arquitectura (Markdown)"}
        </button>
        {archError && (
          <span className="error" role="alert">
            {archError}
          </span>
        )}
      </div>

      {arch && (
        <details className="arch-preview">
          <summary>Vista del mapa ({arch.nodes.length} nodos, {arch.edges.length} enlaces)</summary>
          <pre>{arch.mermaid}</pre>
        </details>
      )}
    </section>
  );
}