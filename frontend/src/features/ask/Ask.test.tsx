import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, afterEach } from "vitest";
import Ask from "./Ask";
afterEach(() => vi.restoreAllMocks());
describe("Project questions", () => {
  it("shows a cited answer after submitting a question", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: "PostgreSQL is configured.",
          status: "VERIFIED",
          confidence: 0.95,
          evidence: [],
          limitations: ["Static inspection only."],
          provider: "offline",
        }),
      }),
    );
    const user = userEvent.setup();
    render(
      <Ask projectId="p" snapshotId="s" onOpen={vi.fn()} onError={vi.fn()} />,
    );
    await user.type(
      screen.getByLabelText("Project question"),
      "Which database?",
    );
    await user.click(screen.getByRole("button", { name: "Ask project" }));
    expect(
      await screen.findByText("PostgreSQL is configured."),
    ).toBeInTheDocument();
    expect(screen.getByText("Static inspection only.")).toBeInTheDocument();
  });
  it("reports provider errors and re-enables submission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ error: { message: "Provider quota reached." } }),
      }),
    );
    const onError = vi.fn(),
      user = userEvent.setup();
    render(
      <Ask projectId="p" snapshotId="s" onOpen={vi.fn()} onError={onError} />,
    );
    await user.type(screen.getByLabelText("Project question"), "Explain auth");
    await user.click(screen.getByRole("button", { name: "Ask project" }));
    expect(onError).toHaveBeenCalledWith("Provider quota reached.");
    expect(screen.getByRole("button", { name: "Ask project" })).toBeEnabled();
  });
});
