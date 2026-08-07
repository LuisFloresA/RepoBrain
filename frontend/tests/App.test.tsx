import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import type { Repo } from "../src/api/types";
import {
  createRepo,
  getFile,
  getRepoStatus,
  getRepos,
  searchRepo,
} from "../src/api/client";

vi.mock("../src/api/client", () => ({
  getRepos: vi.fn(),
  createRepo: vi.fn(),
  getRepoStatus: vi.fn(),
  getFile: vi.fn(),
  searchRepo: vi.fn(),
  askQuestion: vi.fn(),
}));

vi.mock("../src/components/CodeViewer", () => ({
  CodeViewer: (props: { file: { path: string }; highlightLine?: number }) => (
    <div data-testid="code-viewer">
      {props.file.path}:{props.highlightLine}
    </div>
  ),
}));

const demoRepo: Repo = {
  id: "demo1",
  name: "Demo · login-api",
  url: null,
  source: "demo",
  status: "ready",
  progress: 100,
  message: "3 archivos, 5 chunks",
  file_count: 3,
  chunk_count: 5,
  created_at: "2026-01-01T00:00:00Z",
};

const sampleResults = [
  {
    chunk_id: "c1",
    path: "app/auth.py",
    start_line: 3,
    end_line: 5,
    snippet: "def verify_jwt(token):\n    return jwt.decode(token)",
    score: 0.92,
    bm25_score: 0.8,
    semantic_score: 0.6,
  },
];

beforeEach(() => {
  vi.mocked(getRepos).mockResolvedValue([demoRepo]);
  vi.mocked(searchRepo).mockResolvedValue({
    query: "jwt",
    repo_id: "demo1",
    top_k: 10,
    results: sampleResults,
  });
  vi.mocked(getFile).mockResolvedValue({
    path: "app/auth.py",
    language: "python",
    content: "def verify_jwt(token):\n    return jwt.decode(token)",
    line_count: 2,
  });
  vi.mocked(createRepo).mockResolvedValue({ ...demoRepo, status: "indexing", progress: 5 });
  vi.mocked(getRepoStatus).mockResolvedValue({ ...demoRepo, status: "ready" });
});

describe("App", () => {
  it("muestra el buscador y el repo demo", async () => {
    render(<App />);
    expect(await screen.findByPlaceholderText(/Pregunta en lenguaje natural/)).toBeInTheDocument();
    expect(screen.getByText("Probar ahora")).toBeInTheDocument();
    expect(await screen.findByText("Demo · login-api")).toBeInTheDocument();
  });

  it("realiza una búsqueda y muestra resultados con score", async () => {
    const user = userEvent.setup();
    render(<App />);
    const input = await screen.findByPlaceholderText(/Pregunta en lenguaje natural/);
    await waitFor(() => expect(input).toBeEnabled());
    await user.type(input, "jwt");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    expect(await screen.findByText("app/auth.py")).toBeInTheDocument();
    expect(screen.getByText(":3")).toBeInTheDocument();
    expect(await screen.findByText("92")).toBeInTheDocument();
    expect(searchRepo).toHaveBeenCalledWith("demo1", "jwt");
  });

  it("muestra el visor al hacer clic en un resultado", async () => {
    const user = userEvent.setup();
    render(<App />);
    const input = await screen.findByPlaceholderText(/Pregunta en lenguaje natural/);
    await waitFor(() => expect(input).toBeEnabled());
    await user.type(input, "jwt");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    const row = await screen.findByRole("button", { name: /app\/auth\.py/ });
    await user.click(row);

    await waitFor(() => {
      expect(screen.getByTestId("code-viewer")).toHaveTextContent("app/auth.py:3");
    });
    expect(getFile).toHaveBeenCalledWith("demo1", "app/auth.py");
  });

  it("crea el repo demo cuando no hay ninguno y se pulsa Probar ahora", async () => {
    vi.mocked(getRepos).mockResolvedValue([]);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByTestId("demo-button"));

    await waitFor(() => {
      expect(createRepo).toHaveBeenCalledWith(
        expect.objectContaining({ source: "demo" }),
      );
    });
  });

  it("muestra la barra de progreso mientras indexa", async () => {
    const indexingRepo: Repo = { ...demoRepo, status: "indexing", progress: 40, message: "Parseando…" };
    vi.mocked(getRepos).mockResolvedValue([indexingRepo]);
    vi.mocked(getRepoStatus).mockResolvedValue({ ...demoRepo, status: "ready" });

    render(<App />);

    expect(await screen.findByText(/Parseando…/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });
});
