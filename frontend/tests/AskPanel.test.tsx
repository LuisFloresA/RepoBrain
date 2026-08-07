import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { askQuestion } from "../src/api/client";
import type { AskResponse } from "../src/api/types";
import { AskPanel } from "../src/components/AskPanel";

vi.mock("../src/api/client", () => ({
  askQuestion: vi.fn(),
}));

const mockAnswer: AskResponse = {
  question: "¿cómo se hace el soft delete?",
  answer: "La respuesta está en app/models.py.",
  citations: [{ path: "app/models.py", start_line: 27, end_line: 29 }],
  llm: "mock",
  source: "mock",
};

beforeEach(() => {
  vi.mocked(askQuestion).mockResolvedValue(mockAnswer);
});

describe("AskPanel", () => {
  it("hace la pregunta y muestra la respuesta con citas", async () => {
    const user = userEvent.setup();
    render(<AskPanel repoId="r1" onOpenFile={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/soft delete/);
    await user.type(textarea, "¿cómo se hace el soft delete?");
    await user.click(screen.getByTestId("ask-submit"));

    expect(askQuestion).toHaveBeenCalledWith("r1", "¿cómo se hace el soft delete?");

    expect(
      await screen.findByText(/La respuesta está en app\/models\.py/),
    ).toBeInTheDocument();
    expect(await screen.findByText("app/models.py:27")).toBeInTheDocument();
  });

  it("abre el archivo citado al pulsar el enlace de cita", async () => {
    const user = userEvent.setup();
    const onOpenFile = vi.fn();
    render(<AskPanel repoId="r1" onOpenFile={onOpenFile} />);

    await user.type(
      screen.getByPlaceholderText(/soft delete/),
      "¿cómo se hace el soft delete?",
    );
    await user.click(screen.getByTestId("ask-submit"));

    await user.click(await screen.findByText("app/models.py:27"));
    expect(onOpenFile).toHaveBeenCalledWith("app/models.py", 27);
  });

  it("deshabilita el botón mientras el repo no está listo", () => {
    render(<AskPanel repoId="r1" onOpenFile={vi.fn()} disabled />);
    expect(screen.getByTestId("ask-submit")).toBeDisabled();
    expect(screen.getByPlaceholderText(/soft delete/)).toBeDisabled();
  });

  it("muestra error si la petición falla", async () => {
    vi.mocked(askQuestion).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    render(<AskPanel repoId="r1" onOpenFile={vi.fn()} />);

    await user.type(
      screen.getByPlaceholderText(/soft delete/),
      "¿cómo se hace el soft delete?",
    );
    await user.click(screen.getByTestId("ask-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});
