import type { SearchResult } from "../api/types";

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const tone = pct >= 70 ? "high" : pct >= 40 ? "mid" : "low";
  return (
    <span className={`score-badge ${tone}`} title={`Score ${pct}%`}>
      {pct}
    </span>
  );
}

interface ResultsListProps {
  results: SearchResult[];
  query: string;
  onSelect: (result: SearchResult) => void;
}

export function ResultsList({ results, query, onSelect }: ResultsListProps) {
  if (results.length === 0) {
    return (
      <div className="empty-results-card">
        <h3>Sin resultados</h3>
        <p className="no-results">
          No se encontraron fragmentos para &ldquo;{query}&rdquo;.
        </p>
        <ul className="empty-results-tips">
          <li>Prueba con palabras clave más generales.</li>
          <li>Utiliza nombres de archivos, funciones o clases específicas.</li>
          <li>Si el código está en inglés, intenta términos en inglés (ej. auth, handler, parse).</li>
        </ul>
      </div>
    );
  }
  return (
    <ol className="results-list" aria-label="Resultados">
      {results.map((r) => (
        <li key={`${r.chunk_id}-${r.start_line}`}>
          <button
            type="button"
            className="result-row"
            onClick={() => onSelect(r)}
          >
            <ScoreBadge score={r.score} />
            <span className="result-body">
              <span className="result-path">
                {r.path}
                <span className="result-line">:{r.start_line}</span>
              </span>
              <span className="result-snippet">{r.snippet}</span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
