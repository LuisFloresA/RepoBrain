import { afterEach, describe, expect, it, vi } from "vitest";
import { searchRepo } from "../src/api/client";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("devuelve resultados de búsqueda", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ query: "jwt", repo_id: "r1", top_k: 10, results: [] }),
      }),
    );
    const res = await searchRepo("r1", "jwt", 10);
    expect(res.repo_id).toBe("r1");
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain("/api/repos/r1/search?q=jwt&top_k=10");
  });

  it("lanza error con el detalle del backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({ detail: "Repo en estado: indexing" }),
      }),
    );
    await expect(searchRepo("r1", "jwt")).rejects.toThrow("Repo en estado: indexing");
  });

  it("codifica el path del archivo en la URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ path: "app/auth.py", language: "python", content: "", line_count: 0 }),
      }),
    );
    const { getFile } = await import("../src/api/client");
    await getFile("r1", "app/auth.py");
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toBe(
      "/api/repos/r1/files/app/auth.py",
    );
  });

  it("borra un repo con DELETE y keepalive", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ message: "Repo eliminado" }) }),
    );
    const { deleteRepo } = await import("../src/api/client");
    await deleteRepo("r1", true);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe("/api/repos/r1");
    expect(init).toMatchObject({ method: "DELETE", keepalive: true });
  });

  it("limpia todos los repos con DELETE en el raíz", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ message: "2 repos eliminados" }) }),
    );
    const { cleanupRepos } = await import("../src/api/client");
    await cleanupRepos();
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe("/api/repos");
    expect(init?.method).toBe("DELETE");
  });

  it("obtiene ramas de un repositorio remoto", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          url: "https://github.com/usuario/repo.git",
          default_branch: "main",
          branches: ["main", "develop"],
        }),
      }),
    );
    const { getRepoBranches } = await import("../src/api/client");
    const res = await getRepoBranches("https://github.com/usuario/repo.git");
    expect(res.default_branch).toBe("main");
    expect(res.branches).toEqual(["main", "develop"]);
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain("/api/repos/branches?url=https%3A%2F%2Fgithub.com%2Fusuario%2Frepo.git");
  });
});
