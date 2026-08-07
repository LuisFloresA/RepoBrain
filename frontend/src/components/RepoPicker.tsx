import type { Repo } from "../api/types";

interface RepoPickerProps {
  repos: Repo[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
}

export function RepoPicker({ repos, activeId, onSelect, onAdd }: RepoPickerProps) {
  return (
    <aside className="repo-picker" aria-label="Repositorios">
      <h2>Repos</h2>
      <button type="button" className="add-repo" onClick={onAdd}>
        + Indexar por URL
      </button>
      <ul>
        {repos.map((repo) => (
          <li key={repo.id}>
            <button
              type="button"
              className={repo.id === activeId ? "active" : ""}
              onClick={() => onSelect(repo.id)}
            >
              <span className="repo-name">{repo.name}</span>
              <span className={`repo-status ${repo.status}`}>{repo.status}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
