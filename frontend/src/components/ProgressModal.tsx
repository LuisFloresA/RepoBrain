import type { Repo } from "../api/types";

interface ProgressModalProps {
  repo: Repo;
  onClose: () => void;
}

export function ProgressModal({ repo, onClose }: ProgressModalProps) {
  const failed = repo.status === "failed";
  return (
    <div className="progress-modal-backdrop" role="presentation">
      <div
        className="progress-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Cargando repositorio"
      >
        <h2 className="progress-modal-title">
          {failed
            ? "No se pudo cargar el repositorio"
            : "Cargando repositorio…"}
        </h2>
        <p className="progress-modal-name">{repo.name}</p>
        <div className="progress-bar" role="progressbar" aria-valuenow={repo.progress}>
          <div className="progress-fill" style={{ width: `${repo.progress}%` }} />
          <span>
            {repo.status} · {Math.round(repo.progress)}% · {repo.message ?? ""}
          </span>
        </div>
        {failed && (
          <button
            type="button"
            className="progress-modal-close"
            onClick={onClose}
            data-testid="progress-modal-close"
          >
            Cerrar
          </button>
        )}
      </div>
    </div>
  );
}
