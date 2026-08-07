import { useEffect, useState } from "react";
import { fetchHealth, type HealthStatus } from "./api/client";

export function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchHealth("/health")
      .then((h) => {
        if (active) setHealth(h);
      })
      .catch((e: unknown) => {
        if (active) {
          setError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "2rem 1rem" }}>
      <header>
        <h1>RepoBrain</h1>
<p lang="es">
          Búsqueda semántica y Q&amp;A sobre código de fuente. El backend está
          conectado.
        </p>
      </header>

      <section aria-label="Estado del backend">
        <h2>Backend</h2>
        {error ? (
          <p className="error">Error conectando con el backend: {error}</p>
        ) : health ? (
          <dl>
            <div>
              <dt>Servicio</dt>
              <dd>{health.service}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd className={`badge ${health.status}`}>{health.status}</dd>
            </div>
            <div>
              <dt>Entorno</dt>
              <dd>{health.environment}</dd>
            </div>
          </dl>
        ) : (
          <p>Comprobando el backend…</p>
        )}
      </section>
    </main>
  );
}