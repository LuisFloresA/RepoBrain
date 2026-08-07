import { useState } from "react";
import { askQuestion } from "../api/client";
import type { AskResponse, Citation } from "../api/types";

interface AskPanelProps {
  repoId: string;
  onOpenFile: (path: string, line: number) => void;
  disabled?: boolean;
}

function CitationLink({
  citation,
  onOpenFile,
}: {
  citation: Citation;
  onOpenFile: (path: string, line: number) => void;
}) {
  return (
    <button
      type="button"
      className="citation-link"
      title="Abrir el archivo en la línea citada"
      onClick={() => onOpenFile(citation.path, citation.start_line)}
    >
      {citation.path}:{citation.start_line}
    </button>
  );
}

export function AskPanel({ repoId, onOpenFile, disabled }: AskPanelProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = question.trim().length >= 3 && !loading;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const res = await askQuestion(repoId, question.trim());
      setAnswer(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="ask-panel" aria-label="Pregunta al código">
      <h2 className="ask-title">Pregunta al código</h2>
      <div className="ask-form">
        <label className="visually-hidden" htmlFor="ask-input">
          Pregunta sobre el repositorio
        </label>
        <textarea
          id="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="p. ej. ¿cómo se hace el soft delete?"
          rows={2}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={disabled || !canSubmit}
          data-testid="ask-submit"
        >
          {loading ? "Respondiendo…" : "Preguntar"}
        </button>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {answer && (
        <div className="ask-answer">
          <p className="ask-source">
            Respuesta generada · motor: {answer.llm || answer.source}
          </p>
          <div className="answer-text">
            {answer.answer.split("\n").map((line, i) => (
              <p key={i}>{line || "\u00A0"}</p>
            ))}
          </div>
          {answer.citations.length > 0 && (
            <ul className="citation-list" aria-label="Citas">
              {answer.citations.map((c) => (
                <li key={`${c.path}:${c.start_line}`}>
                  <CitationLink citation={c} onOpenFile={onOpenFile} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
