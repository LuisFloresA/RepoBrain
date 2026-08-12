import { useEffect, useRef, useState } from "react";
import { getRepoBranches } from "../api/client";

interface RepoSetupProps {
  onIndex: (url: string, branch: string) => void;
  onDemo: () => void;
  disabled?: boolean;
}

export function RepoSetup({ onIndex, onDemo, disabled }: RepoSetupProps) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [branches, setBranches] = useState<string[]>([]);
  const [defaultBranch, setDefaultBranch] = useState<string | null>(null);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [branchesError, setBranchesError] = useState<string | null>(null);
  const [isCustomBranch, setIsCustomBranch] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeUrlRef = useRef<string>("");

  useEffect(() => {
    const trimmed = url.trim();

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    if (
      !trimmed ||
      (!trimmed.startsWith("http://") &&
        !trimmed.startsWith("https://") &&
        !trimmed.startsWith("git@") &&
        !trimmed.startsWith("ssh://"))
    ) {
      setBranches([]);
      setDefaultBranch(null);
      setBranchesError(null);
      setLoadingBranches(false);
      setIsCustomBranch(false);
      activeUrlRef.current = "";
      return;
    }

    if (trimmed === activeUrlRef.current) {
      return;
    }

    setLoadingBranches(true);
    setBranchesError(null);

    timerRef.current = setTimeout(async () => {
      try {
        const data = await getRepoBranches(trimmed);
        activeUrlRef.current = trimmed;
        setBranches(data.branches);
        setDefaultBranch(data.default_branch);
        setBranchesError(null);
        setIsCustomBranch(false);
        if (data.default_branch) {
          setBranch(data.default_branch);
        } else if (data.branches.length > 0) {
          setBranch(data.branches[0]);
        }
      } catch (err) {
        setBranches([]);
        setDefaultBranch(null);
        setBranchesError(
          err instanceof Error ? err.message : "No se pudieron listar las ramas"
        );
      } finally {
        setLoadingBranches(false);
      }
    }, 450);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [url]);

  const handleBranchSelectChange = (val: string) => {
    if (val === "__custom__") {
      setIsCustomBranch(true);
      setBranch("");
    } else {
      setIsCustomBranch(false);
      setBranch(val);
    }
  };

  const handleManualSwitchBack = () => {
    setIsCustomBranch(false);
    if (defaultBranch) {
      setBranch(defaultBranch);
    } else if (branches.length > 0) {
      setBranch(branches[0]);
    }
  };

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
        <div className="repo-setup-fields">
          <input
            type="url"
            className="repo-setup-url-input"
            placeholder="https://github.com/usuario/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="URL del repositorio"
            disabled={disabled}
            required
          />

          <div className="repo-setup-branch-wrapper">
            {loadingBranches ? (
              <div className="repo-setup-branch-loading" aria-live="polite">
                <span className="spinner-dots" aria-hidden="true"></span>
                <span>Buscando ramas…</span>
              </div>
            ) : branches.length > 0 && !isCustomBranch ? (
              <select
                className="repo-setup-branch-select"
                value={branch}
                onChange={(e) => handleBranchSelectChange(e.target.value)}
                aria-label="Rama del repositorio"
                disabled={disabled}
                data-testid="branch-select"
              >
                {defaultBranch && (
                  <option value={defaultBranch}>
                    {defaultBranch} (por defecto)
                  </option>
                )}
                {branches
                  .filter((b) => b !== defaultBranch)
                  .map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                <option value="__custom__"> Otra rama (escribir manualmente)...</option>
              </select>
            ) : (
              <div className="repo-setup-manual-branch">
                <input
                  type="text"
                  className="repo-setup-branch-input"
                  placeholder="rama (opcional, ej. develop)"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  aria-label="Rama del repositorio"
                  disabled={disabled}
                  data-testid="branch-input"
                />
                {branches.length > 0 && isCustomBranch && (
                  <button
                    type="button"
                    className="repo-setup-toggle-btn"
                    onClick={handleManualSwitchBack}
                    title="Volver a la lista de ramas desplegable"
                  >
                    Listar ramas
                  </button>
                )}
              </div>
            )}
          </div>

          <button type="submit" disabled={disabled || !url.trim()}>
            Indexar repo
          </button>
        </div>

        {branches.length > 0 && !isCustomBranch && (
          <div className="repo-setup-status-row">
            <span className="repo-setup-badge-ok">
              {branches.length} rama{branches.length > 1 ? "s" : ""} encontrada{branches.length > 1 ? "s" : ""}
            </span>
          </div>
        )}

        {branchesError && url.trim().length > 10 && (
          <div className="repo-setup-status-row">
            <span className="repo-setup-badge-warn">
              {branchesError} (puedes indicar la rama manualmente)
            </span>
          </div>
        )}
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
