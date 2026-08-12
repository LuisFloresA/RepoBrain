import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RepoSetup } from "../src/components/RepoSetup";
import { getRepoBranches } from "../src/api/client";

vi.mock("../src/api/client", () => ({
  getRepoBranches: vi.fn(),
}));

describe("RepoSetup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza campos iniciales y botón demo", () => {
    render(<RepoSetup onIndex={vi.fn()} onDemo={vi.fn()} />);

    expect(screen.getByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/rama \(opcional, ej\. develop\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Indexar repo" })).toBeDisabled();
    expect(screen.getByTestId("use-demo")).toBeInTheDocument();
  });

  it("consulta y muestra la lista de ramas al ingresar una URL de GitHub", async () => {
    const user = userEvent.setup();
    vi.mocked(getRepoBranches).mockResolvedValue({
      url: "https://github.com/usuario/repo",
      default_branch: "main",
      branches: ["main", "develop", "feature/auth"],
    });

    const onIndex = vi.fn();
    render(<RepoSetup onIndex={onIndex} onDemo={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/);
    await user.type(urlInput, "https://github.com/usuario/repo");

    await waitFor(() => {
      expect(screen.getByTestId("branch-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("branch-select") as HTMLSelectElement;
    expect(select.value).toBe("main");
    expect(screen.getByText("main (por defecto)")).toBeInTheDocument();
    expect(screen.getByText("develop")).toBeInTheDocument();
    expect(screen.getByText("feature/auth")).toBeInTheDocument();
    expect(screen.getByText(/3 ramas encontradas/)).toBeInTheDocument();

    // Seleccionar otra rama
    await user.selectOptions(select, "develop");
    expect(select.value).toBe("develop");

    // Indexar repo con la rama seleccionada
    await user.click(screen.getByRole("button", { name: "Indexar repo" }));
    expect(onIndex).toHaveBeenCalledWith("https://github.com/usuario/repo", "develop");
  });

  it("permite cambiar a entrada manual y luego volver al dropdown", async () => {
    const user = userEvent.setup();
    vi.mocked(getRepoBranches).mockResolvedValue({
      url: "https://github.com/usuario/repo",
      default_branch: "main",
      branches: ["main", "develop"],
    });

    const onIndex = vi.fn();
    render(<RepoSetup onIndex={onIndex} onDemo={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/);
    await user.type(urlInput, "https://github.com/usuario/repo");

    await waitFor(() => {
      expect(screen.getByTestId("branch-select")).toBeInTheDocument();
    });

    // Seleccionar opción de escribir manualmente
    await user.selectOptions(screen.getByTestId("branch-select"), "__custom__");

    // Debe mostrarse el input de texto
    const branchInput = screen.getByTestId("branch-input");
    expect(branchInput).toBeInTheDocument();
    await user.type(branchInput, "release/1.0");

    // Subir con la rama manual
    await user.click(screen.getByRole("button", { name: "Indexar repo" }));
    expect(onIndex).toHaveBeenCalledWith("https://github.com/usuario/repo", "release/1.0");

    // Botón para volver a listar ramas
    const toggleBtn = screen.getByRole("button", { name: "Listar ramas" });
    await user.click(toggleBtn);
    expect(screen.getByTestId("branch-select")).toBeInTheDocument();
  });

  it("muestra advertencia y mantiene entrada manual si la consulta de ramas falla", async () => {
    const user = userEvent.setup();
    vi.mocked(getRepoBranches).mockRejectedValue(new Error("Repositorio no accesible"));

    render(<RepoSetup onIndex={vi.fn()} onDemo={vi.fn()} />);

    const urlInput = screen.getByPlaceholderText(/https:\/\/github\.com\/usuario\/repo/);
    await user.type(urlInput, "https://github.com/usuario/privado");

    await waitFor(() => {
      expect(screen.getByText(/Repositorio no accesible/)).toBeInTheDocument();
    });

    expect(screen.getByTestId("branch-input")).toBeInTheDocument();
  });

  it("llama a onDemo al pulsar el botón de demo", async () => {
    const user = userEvent.setup();
    const onDemo = vi.fn();
    render(<RepoSetup onIndex={vi.fn()} onDemo={onDemo} />);

    await user.click(screen.getByTestId("use-demo"));
    expect(onDemo).toHaveBeenCalledTimes(1);
  });
});
