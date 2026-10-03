import { useEffect, useState } from "react";
import { FileCode2, Search } from "lucide-react";
import { api } from "../../services/api";
import type { FileContent, SourceFile, Evidence } from "../../types";
import { Loading, PageHeading } from "../../components/ui";
export default function Explorer({
  projectId,
  snapshotId,
  focus,
  onError,
}: {
  projectId: string;
  snapshotId: string;
  focus: Evidence | null;
  onError: (s: string) => void;
}) {
  const [files, setFiles] = useState<SourceFile[]>([]),
    [total, setTotal] = useState(0),
    [source, setSource] = useState<FileContent | null>(null),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false);
  const defaultFileId = files[0]?.id;
  useEffect(() => {
    let live = true;
    api<{ items: SourceFile[]; total: number }>(
      `/projects/${projectId}/files?snapshot_id=${snapshotId}&limit=200`,
    )
      .then((d) => {
        if (live) {
          setFiles(d.items);
          setTotal(d.total);
        }
      })
      .catch((e) => onError(e.message));
    return () => {
      live = false;
    };
  }, [projectId, snapshotId, onError]);
  const open = (id: string) => {
    setBusy(true);
    api<FileContent>(`/projects/${projectId}/files/${id}`)
      .then(setSource)
      .catch((e) => onError(e.message))
      .finally(() => setBusy(false));
  };
  useEffect(() => {
    const id = focus?.file_id ?? defaultFileId;
    if (!id) return;
    let live = true;
    setBusy(true);
    api<FileContent>(`/projects/${projectId}/files/${id}`)
      .then((d) => {
        if (live) setSource(d);
      })
      .catch((e) => onError(e.message))
      .finally(() => {
        if (live) setBusy(false);
      });
    return () => {
      live = false;
    };
  }, [focus, defaultFileId, projectId, onError]);
  const more = async () => {
    try {
      const d = await api<{ items: SourceFile[]; total: number }>(
        `/projects/${projectId}/files?snapshot_id=${snapshotId}&limit=200&offset=${files.length}`,
      );
      setFiles([...files, ...d.items]);
    } catch (e) {
      onError((e as Error).message);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="PROVENANCE"
        title="Evidence explorer"
        description="Inspect exactly what was analyzed. Sensitive values are redacted."
      />
      <div className="explorer">
        <aside className="file-tree">
          <label className="search">
            <Search size={15} />
            <input
              aria-label="Find file"
              placeholder="Filter files…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="tree-caption mono">{total} ANALYZED FILES</div>
          {files
            .filter((f) => f.path.toLowerCase().includes(query.toLowerCase()))
            .map((f) => (
              <button
                key={f.id}
                className={source?.id === f.id ? "active" : ""}
                onClick={() => open(f.id)}
              >
                <FileCode2 size={15} />
                <span>{f.path}</span>
              </button>
            ))}
          {files.length < total && (
            <button onClick={more}>Load more files</button>
          )}
        </aside>
        <section className="source-pane">
          <header>
            <span className="mono">{source?.path ?? "Select a file"}</span>
            <span className="muted">{source?.language}</span>
          </header>
          {busy ? (
            <Loading />
          ) : (
            source && (
              <div
                className="source-code"
                tabIndex={0}
                aria-label="Source code"
              >
                {source.content.split("\n").map((line, i) => (
                  <div
                    className={
                      focus?.file_id === source.id &&
                      i + 1 >= focus.start_line &&
                      i + 1 <= focus.end_line
                        ? "code-line highlighted"
                        : "code-line"
                    }
                    key={i}
                  >
                    <span className="line-number">{i + 1}</span>
                    <code>{line || " "}</code>
                  </div>
                ))}
              </div>
            )
          )}
          <footer className="mono muted">
            Read-only evidence · snapshot {snapshotId.slice(0, 8)} · uploaded
            code is never executed
          </footer>
        </section>
      </div>
    </>
  );
}
