import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getArchitecture } from "../src/api/client";
import type { Repo } from "../src/api/types";
import { MetricsPanel } from "../src/components/MetricsPanel";

vi.mock("../src/api/client", () => ({
  getArchitecture: vi.fn(),
}));

const readyRepo: Repo = {
  id: "r1",
  name: "login-api",
  url: "https://github.com/u/login-api.git",
  branch: "develop",
  source: "url",
  status: "ready",
  progress: 100,
  message: "2 archivos, 4 chunks · 1 archivo modificado",
  file_count: 2,
  chunk_count: 4,
  source_rev: "a1b2c3d4e5",
  indexed_files: 2,
  skipped_files: 1,
  indexed_bytes: 12345,
  last_indexed_at: "2026-01-02T10:00:00Z",
  stats: {
    by_language: { python: 3, java: 1 },
    skipped_reasons: { sin_lenguaje: 1 },
  },
  last_changes: {
    full: false,
    count: 1,
    files: [{ path: "app/auth.py", status: "modificado" }],
    commits: ["evolucion"],
  },
  created_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(getArchitecture).mockResolvedValue({
    repo_id: "r1",
    nodes: [
      { id: "f0", label: "app/auth.py", kind: "file", path: "app/auth.py", line: 1 },
      { id: "n1", label: "verify_jwt", kind: "function", path: "app/auth.py", line: 3 },
    ],
    edges: [{ source: "f0", target: "n1" }],
    mermaid: "graph TD\n    f0([\"app/auth.py\"])\n    f0 --> n1",
    markdown: "# Mapa de arquitectura — login-api\n\n- `verify_jwt` (línea 3)",
  });
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:test"),
    revokeObjectURL: vi.fn(),
  });
});

describe("MetricsPanel", () => {
  it("muestra métricas de cobertura y la rama indexada", () => {
    render(<MetricsPanel repo={readyRepo} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("12.1 KB")).toBeInTheDocument();
    expect(screen.getByText("develop")).toBeInTheDocument();
    expect(screen.getByText("python", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText("java", { selector: "code" })).toBeInTheDocument();
  });

  it("muestra qué cambió en la última indexación", () => {
    render(<MetricsPanel repo={readyRepo} />);
    expect(screen.getByText("app/auth.py")).toBeInTheDocument();
    expect(screen.getByText("modificado")).toBeInTheDocument();
    expect(screen.getByText(/evolucion/)).toBeInTheDocument();
  });

  it("indica reindexado completo cuando last_changes.full", () => {
    const fullRepo: Repo = {
      ...readyRepo,
      last_changes: { full: true, count: null, files: null, commits: null },
    };
    render(<MetricsPanel repo={fullRepo} />);
    expect(screen.getByText(/reindexado completo/)).toBeInTheDocument();
  });

it("exporta el mapa de arquitectura como descarga de Markdown", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const user = userEvent.setup();
    render(<MetricsPanel repo={readyRepo} />);
    await user.click(
      screen.getByRole("button", { name: "Exportar mapa de arquitectura (Markdown)" }),
    );

    await waitFor(() => expect(getArchitecture).toHaveBeenCalledWith("r1"));
    await waitFor(() => {
      expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    });
    const [blob] = vi.mocked(URL.createObjectURL).mock.calls[0] as unknown as [Blob];
    expect(blob.type).toBe("text/markdown;charset=utf-8");
    expect(blob.size).toBeGreaterThan(0);
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalled());
    expect(String(vi.mocked(URL.revokeObjectURL).mock.calls[0][0])).toContain("blob:");
  });

  it("deshabilita la exportación si el repo aún no está listo", async () => {
    const indexing: Repo = { ...readyRepo, status: "indexing" };
    render(<MetricsPanel repo={indexing} />);
    expect(
      screen.getByRole("button", { name: "Exportar mapa de arquitectura (Markdown)" }),
    ).toBeDisabled();
  });

  it("muestra error si la exportación falla", async () => {
    vi.mocked(getArchitecture).mockRejectedValue(new Error("Checkout no disponible"));
    const user = userEvent.setup();
    render(<MetricsPanel repo={readyRepo} />);
    await user.click(
      screen.getByRole("button", { name: "Exportar mapa de arquitectura (Markdown)" }),
    );
    expect(await screen.findByText("Checkout no disponible")).toBeInTheDocument();
  });
});