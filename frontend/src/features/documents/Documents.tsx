import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";
import type { Doc } from "../../types";
import { api, post } from "../../services/api";
import { PageHeading } from "../../components/ui";
const kinds = [
  ["report", "Academic report"],
  ["presentation", "Learning Block slides"],
  ["readme", "README suggestions"],
  ["resume", "Resume description"],
  ["linkedin", "LinkedIn description"],
  ["viva-notes", "Viva notes"],
];
export default function Documents({
  projectId,
  onError,
}: {
  projectId: string;
  onError: (s: string) => void;
}) {
  const [kind, setKind] = useState("report"),
    [docs, setDocs] = useState<Doc[]>([]),
    [selected, setSelected] = useState<Doc | null>(null),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api<{ items: Doc[] }>(`/projects/${projectId}/documents`)
      .then((d) => setDocs(d.items))
      .catch((e) => onError(e.message));
  }, [projectId, onError]);
  const generate = async () => {
    setBusy(true);
    try {
      const d = await post<Doc>(`/projects/${projectId}/documents`, { kind });
      setSelected(d);
      setDocs([d, ...docs]);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const download = () => {
    if (!selected) return;
    const url = URL.createObjectURL(
      new Blob([selected.content], { type: "text/markdown;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "projecttrace-" + selected.kind + ".md";
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      <PageHeading
        eyebrow="EVIDENCE → DOCUMENTATION"
        title="Document what exists"
        description="Generate a cited draft. Recommendations remain separate from implemented facts."
      />
      <div className="document-layout">
        <aside className="document-sidebar">
          <h3>Create a draft</h3>
          <label className="field">
            Output format
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {kinds.map(([v, l]) => (
                <option value={v} key={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={busy} onClick={generate}>
            {busy ? "Generating…" : "Generate draft"}
            <FileText size={15} />
          </button>
          <p className="small muted">
            Evidence templates work offline. Missing project purpose and
            personal contributions are labeled for author input.
          </p>
          <div className="rule" />
          <h3>Saved drafts</h3>
          {docs.map((d) => (
            <button
              className={"doc-item " + (selected?.id === d.id ? "active" : "")}
              key={d.id}
              onClick={() => setSelected(d)}
            >
              <FileText size={15} />
              <span>
                {kinds.find((k) => k[0] === d.kind)?.[1]}
                <small>{new Date(d.created_at).toLocaleString()}</small>
              </span>
            </button>
          ))}
        </aside>
        <section className="document-preview">
          <header>
            <span className="eyebrow">
              {selected ? "GROUNDED DRAFT" : "DOCUMENT PREVIEW"}
            </span>
            {selected && (
              <button className="secondary" onClick={download}>
                <Download size={15} />
                Download Markdown
              </button>
            )}
          </header>
          {selected ? (
            <pre tabIndex={0} aria-label="Generated document draft">
              {selected.content}
            </pre>
          ) : (
            <div className="empty">
              <FileText size={28} />
              <h2>Start with verified facts.</h2>
              <p>
                Choose a format and generate a draft from the latest analyzed
                snapshot.
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
