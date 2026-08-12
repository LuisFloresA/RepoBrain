import { useState } from "react";

interface RepoSetupProps {
  onIndex: (url: string, branch: string) => void;
  onDemo: () => void;
  disabled?: boolean;
}

export function RepoSetup({ onIndex, onDemo, disabled }: RepoSetupProps) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");

  return (
    <section className="repo-setup" aria-label="Configurar repositorio">
      <h2 className="repo-setup-title">Empezar una búsqueda nueva</h2>
      <p className="repo-setup-sub">
        Pega la URL de un repositorio de GitHub para indexarlo y poder
        preguntar sobre su código. Nada queda guardado: al cerrar la página el
        repositorio se elimina.
      </p>
      <form
        className="repo-setup-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) onIndex(url.trim(), branch.trim());
        }}
      >
        <input
          type="url"
          placeholder="https://github.com/usuario/repo"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-label="URL del repositorio"
          disabled={disabled}
        />
        <input
          type="text"
          placeholder="rama (opcional, ej. develop)"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          aria-label="Rama del repositorio"
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || !url.trim()}>
          Indexar repo
        </button>
      </form>
      <div className="repo-setup-demo">
        <button
          type="button"
          className="demo"
          onClick={onDemo}
          disabled={disabled}
          data-testid="use-demo"
        >
          Usar demo
        </button>
        <span className="repo-setup-demo-hint">
          Prueba la herramienta con un proyecto de ejemplo ya indexado.
        </span>
      </div>
    </section>
  );
}
