import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import type { Repo, SearchResponse } from "../src/api/types";
import {
  cleanupRepos,
  createRepo,
  deleteRepo,
  getFile,
  getRepoStatus,
  searchRepo,
} from "../src/api/client";

vi.mock("../src/api/client", () => ({
  cleanupRepos: vi.fn(),
  createRepo: vi.fn(),
  deleteRepo: vi.fn(),
  getFile: vi.fn(),
  getRepoStatus: vi.fn(),
  searchRepo: vi.fn(),
  askQuestion: vi.fn(),
  getRepoBranches: vi.fn().mockResolvedValue({ url: "", default_branch: null, branches: [] }),
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
  name: "Demo · login-api (JWT)",
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
  vi.mocked(cleanupRepos).mockResolvedValue();
  vi.mocked(deleteRepo).mockResolvedValue();
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
  it("limpia sesiones previas y muestra la pantalla de entrada", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: /Empezar una búsqueda nueva/ })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/)).toBeInTheDocument();
    expect(screen.getByTestId("use-demo")).toBeInTheDocument();
    expect(cleanupRepos).toHaveBeenCalled();
  });

  it("usa el demo, muestra el modal de progreso y luego el buscador", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByTestId("use-demo"));
    expect(createRepo).toHaveBeenCalledWith({ source: "demo", name: "Demo · login-api (JWT)" });

    expect(await screen.findByRole("dialog", { name: "Cargando repositorio" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    await waitFor(
      () => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      },
      { timeout: 4000 },
    );
    expect(screen.getByPlaceholderText(/Pregunta en lenguaje natural/)).toBeInTheDocument();
  });

  it("indexa un repo por URL desde la pantalla de entrada", async () => {
    const user = userEvent.setup();
    render(<App />);

    const urlInput = await screen.findByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/);
    await user.type(urlInput, "https://github.com/luis/api.git");
    await user.click(screen.getByRole("button", { name: "Indexar repo" }));

    expect(createRepo).toHaveBeenCalledWith({
      url: "https://github.com/luis/api.git",
      source: "url",
      branch: null,
    });
    expect(await screen.findByRole("dialog", { name: "Cargando repositorio" })).toBeInTheDocument();
  });

  it("realiza una búsqueda y muestra resultados con score", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByTestId("use-demo"));
    const input = await screen.findByPlaceholderText(/Pregunta en lenguaje natural/);
    await waitFor(() => expect(input).toBeEnabled(), { timeout: 4000 });
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
    await user.click(await screen.findByTestId("use-demo"));
    const input = await screen.findByPlaceholderText(/Pregunta en lenguaje natural/);
    await waitFor(() => expect(input).toBeEnabled(), { timeout: 4000 });
    await user.type(input, "jwt");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    const row = await screen.findByRole("button", { name: /app\/auth\.py/ });
    await user.click(row);

    await waitFor(() => {
      expect(screen.getByTestId("code-viewer")).toHaveTextContent("app/auth.py:3");
    });
    expect(getFile).toHaveBeenCalledWith("demo1", "app/auth.py");
  });

  it("muestra el modal de progreso mientras indexa y el error si falla", async () => {
    const indexingRepo: Repo = { ...demoRepo, status: "indexing", progress: 40, message: "Parseando…" };
    vi.mocked(createRepo).mockResolvedValue(indexingRepo);
    vi.mocked(getRepoStatus).mockResolvedValue({ ...demoRepo, status: "failed", message: "boom" });

    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByTestId("use-demo"));

    expect(await screen.findByRole("dialog", { name: "Cargando repositorio" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    await waitFor(
      () => {
        expect(screen.getByText(/No se pudo cargar el repositorio/)).toBeInTheDocument();
      },
      { timeout: 4000 },
    );
    expect(screen.getByTestId("progress-modal-close")).toBeInTheDocument();
  });

  it("borra el repo de la sesión al cerrar la página", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByTestId("use-demo"));
    await waitFor(() => expect(createRepo).toHaveBeenCalled());

    window.dispatchEvent(new Event("beforeunload"));
    expect(deleteRepo).toHaveBeenCalledWith("demo1", true);
  });

  it("muestra el estado de la API en la barra superior", async () => {
    render(<App />);
    expect(await screen.findByText(/\(API:/)).toBeInTheDocument();
  });

  it("muestra la pantalla de carga durante la búsqueda y estado sin resultados", async () => {
    let resolveSearch: (val: SearchResponse) => void;
    const searchPromise = new Promise<SearchResponse>((resolve) => {
      resolveSearch = resolve;
    });
    vi.mocked(searchRepo).mockReturnValue(searchPromise);

    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByTestId("use-demo"));
    const input = await screen.findByPlaceholderText(/Pregunta en lenguaje natural/);
    await waitFor(() => expect(input).toBeEnabled(), { timeout: 4000 });
    await user.type(input, "termino desconocido");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    // Verifica que se muestra la pantalla de carga de búsqueda
    expect(screen.getByRole("status")).toHaveTextContent("Buscando en el repositorio…");

    // Resuelve con 0 resultados
    resolveSearch!({
      query: "termino desconocido",
      repo_id: "demo1",
      top_k: 10,
      results: [],
    });

    expect(await screen.findByText("Sin resultados")).toBeInTheDocument();
    expect(screen.getByText(/No se encontraron fragmentos para/)).toBeInTheDocument();
  });
});
