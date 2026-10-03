import { statuses } from "../../types";
import { useEffect, useState } from "react";
import { Search, ChevronRight, X } from "lucide-react";
import type { Claim, ClaimStatus, Evidence } from "../../types";
import { EvidenceList, PageHeading, Status } from "../../components/ui";
export default function Claims({
  claims,
  onOpen,
  total,
  onMore,
  loadPage,
  counts,
}: {
  claims: Claim[];
  onOpen: (e: Evidence) => void;
  total: number;
  onMore: () => void;
  loadPage?: (
    status: ClaimStatus | "ALL",
    query: string,
    offset: number,
  ) => Promise<{ items: Claim[]; total: number }>;
  counts?: Partial<Record<ClaimStatus, number>>;
}) {
  const [filter, setFilter] = useState<ClaimStatus | "ALL">("ALL"),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<Claim | null>(null);
  const [result, setResult] = useState<{
    items: Claim[];
    total: number;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    let active = true;
    setResult(null);
    setLoadError("");
    if (!loadPage || (filter === "ALL" && !search.trim())) {
      setBusy(false);
      return;
    }
    setBusy(true);
    const timer = setTimeout(() => {
      loadPage(filter, search.trim(), 0)
        .then((data) => {
          if (active) setResult(data);
        })
        .catch((error) => {
          if (active) setLoadError((error as Error).message);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [filter, search, loadPage]);
  const rows = (result?.items ?? claims).filter(
    (c) =>
      (filter === "ALL" || c.status === filter) &&
      c.text.toLowerCase().includes(search.toLowerCase()),
  );
  const matchedTotal =
    result?.total ??
    (loadPage && (filter !== "ALL" || search.trim()) ? rows.length : total);
  const more = async () => {
    if (!loadPage || !result) {
      onMore();
      return;
    }
    setBusy(true);
    try {
      const data = await loadPage(filter, search.trim(), result.items.length);
      setResult((current) =>
        current === result
          ? { items: [...result.items, ...data.items], total: data.total }
          : current,
      );
    } catch (error) {
      setLoadError((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="VERIFICATION"
        title="Claim ledger"
        description="Every technical statement, traced to its supporting evidence."
      />
      <div className="toolbar">
        <div className="tabs" role="group" aria-label="Filter claims">
          {(["ALL", ...statuses] as const).map((s) => (
            <button
              key={s}
              className={filter === s ? "active" : ""}
              onClick={() => setFilter(s)}
            >
              {s === "ALL"
                ? "All claims"
                : s.charAt(0) + s.slice(1).toLowerCase()}{" "}
              <span>
                {s === "ALL"
                  ? total
                  : (counts?.[s] ??
                    claims.filter((c) => c.status === s).length)}
              </span>
            </button>
          ))}
        </div>
        <label className="search">
          <Search size={15} />
          <input
            aria-label="Search claims"
            placeholder="Find a claim…"
            value={search}
            maxLength={200}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {loadError && (
        <p className="error" role="alert">
          {loadError}
        </p>
      )}
      {busy && <p role="status">Loading matching claims…</p>}
      <div className="table-wrap">
        <table className="claims-table">
          <thead>
            <tr>
              <th>Technical claim</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Evidence</th>
              <th>Source artifact</th>
              <th>Last checked</th>
              <th>
                <span className="sr-only">Inspect</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>
                  <button
                    className="claim-button"
                    onClick={() => setSelected(c)}
                  >
                    {c.text}
                  </button>
                </td>
                <td>
                  <Status value={c.status} />
                </td>
                <td className="mono muted">
                  {Math.round(c.confidence * 100)}%
                </td>
                <td className="mono">
                  {c.evidence.length}{" "}
                  {c.evidence.length === 1 ? "source" : "sources"}
                </td>
                <td className="mono muted">{c.source_artifact}</td>
                <td className="muted">
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td>
                  <button
                    className="icon-btn"
                    aria-label={"Inspect " + c.text}
                    onClick={() => setSelected(c)}
                  >
                    <ChevronRight size={17} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !busy && (
          <div className="no-results">No claims match this filter.</div>
        )}
      </div>
      <div className="table-note">
        Showing {rows.length} of {matchedTotal} claims. Confidence is a
        heuristic score, not a probability of correctness.
        {rows.length < matchedTotal && (
          <button className="text-btn" onClick={more} disabled={busy}>
            Load more claims
          </button>
        )}
      </div>
      {selected && (
        <aside className="inspector" aria-label="Claim evidence inspector">
          <header>
            <div className="eyebrow">EVIDENCE INSPECTOR</div>
            <button
              className="icon-btn"
              onClick={() => setSelected(null)}
              aria-label="Close inspector"
            >
              <X size={18} />
            </button>
          </header>
          <Status value={selected.status} />
          <h2>{selected.text}</h2>
          <p>{selected.explanation}</p>
          <div className="rule" />
          <h3>Source evidence</h3>
          <EvidenceList items={selected.evidence} onOpen={onOpen} />
          {!selected.evidence.length && <p>No current supporting excerpts.</p>}
          <h3>Recommended action</h3>
          <p>
            {selected.recommendation ||
              "Keep the statement scoped to the cited static evidence."}
          </p>
          <footer className="mono muted">
            Snapshot {selected.commit_sha.slice(0, 12)}
            <br />
            {selected.source_artifact}
            {selected.source_line && " · L" + selected.source_line}
          </footer>
        </aside>
      )}
    </>
  );
}
