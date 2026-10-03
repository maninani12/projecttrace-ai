import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Claims from "./Claims";
import type { Claim } from "../../types";
const items: Claim[] = [
  {
    id: "one",
    text: "PostgreSQL configured",
    status: "VERIFIED",
    confidence: 0.95,
    explanation: "Source configuration",
    source_artifact: "Repository",
    source_line: null,
    recommendation: "",
    created_at: "2026-10-03",
    snapshot_id: "snap",
    commit_sha: "abc",
    evidence: [],
  },
  {
    id: "two",
    text: "Uses MongoDB",
    status: "CONTRADICTED",
    confidence: 0.85,
    explanation: "Source uses PostgreSQL",
    source_artifact: "README.md",
    source_line: 2,
    recommendation: "Update database",
    created_at: "2026-10-03",
    snapshot_id: "snap",
    commit_sha: "abc",
    evidence: [],
  },
];
describe("Claim review", () => {
  it("retrieves matching claims outside the initial page", async () => {
    const user = userEvent.setup();
    const loadPage = vi.fn().mockResolvedValue({ items: [items[1]], total: 1 });
    render(
      <Claims
        claims={[items[0]]}
        total={60}
        counts={{ CONTRADICTED: 1 }}
        loadPage={loadPage}
        onOpen={vi.fn()}
        onMore={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Contradicted 1/i }));
    expect(
      await screen.findByRole("button", { name: "Uses MongoDB" }),
    ).toBeInTheDocument();
    expect(loadPage).toHaveBeenCalledWith("CONTRADICTED", "", 0);
    await user.click(screen.getByRole("button", { name: /All claims 60/i }));
    expect(
      await screen.findByRole("button", { name: "PostgreSQL configured" }),
    ).toBeInTheDocument();
  });
  it("filters claims and opens the evidence inspector", async () => {
    const user = userEvent.setup();
    render(
      <Claims claims={items} total={2} onOpen={vi.fn()} onMore={vi.fn()} />,
    );
    await user.click(screen.getByRole("button", { name: /Contradicted 1/i }));
    expect(screen.queryByText("PostgreSQL configured")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Uses MongoDB" }));
    expect(screen.getByLabelText("Claim evidence inspector")).toHaveTextContent(
      "Source uses PostgreSQL",
    );
    expect(screen.getByText("Update database")).toBeInTheDocument();
  });
  it("renders empty search results and literal untrusted strings safely", async () => {
    const user = userEvent.setup();
    render(
      <Claims
        claims={[{ ...items[0], text: "<script>alert(1)</script>" }]}
        total={1}
        onOpen={vi.fn()}
        onMore={vi.fn()}
      />,
    );
    expect(document.querySelector("script")).toBeNull();
    await user.type(
      screen.getByRole("textbox", { name: "Search claims" }),
      "absent",
    );
    expect(
      screen.getByText("No claims match this filter."),
    ).toBeInTheDocument();
  });
});
