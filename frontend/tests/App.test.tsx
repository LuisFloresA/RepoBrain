import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  it("muestra el estado del backend cuando el health responde OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "ok",
          service: "RepoBrain",
          environment: "development",
        }),
      }),
    );

    render(<App />);

    expect(await screen.findByText("RepoBrain")).toBeInTheDocument();
    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(screen.getByText("development")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("muestra un error cuando el backend no responde", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    );

    render(<App />);

    expect(
      await screen.findByText(/Error conectando con el backend/),
    ).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});