import { useState } from "react";
import { ChevronLeft, ChevronRight, Bookmark, Eye } from "lucide-react";
import type { Evidence, VivaSession } from "../../types";
import { api, post } from "../../services/api";
import { EvidenceList, PageHeading } from "../../components/ui";
const levels = [
  "BEGINNER",
  "FACULTY",
  "TECHNICAL REVIEWER",
  "RECRUITER",
  "ADVERSARIAL EXAMINER",
];
export default function Viva({
  projectId,
  onOpen,
  onError,
}: {
  projectId: string;
  onOpen: (e: Evidence) => void;
  onError: (s: string) => void;
}) {
  const [difficulty, setDifficulty] = useState("FACULTY"),
    [session, setSession] = useState<VivaSession | null>(null),
    [index, setIndex] = useState(0),
    [reveal, setReveal] = useState(false),
    [busy, setBusy] = useState(false);
  const question = session?.questions[index];
  const generate = async () => {
    setBusy(true);
    try {
      setSession(
        await post<VivaSession>(`/projects/${projectId}/viva`, { difficulty }),
      );
      setIndex(0);
      setReveal(false);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const move = (n: number) => {
    setIndex(n);
    setReveal(false);
  };
  const mark = async () => {
    if (!session || !question) return;
    try {
      await api(`/projects/${projectId}/viva/${question.id}`, {
        method: "PATCH",
        body: JSON.stringify({ revision: !question.revision }),
      });
      setSession({
        ...session,
        questions: session.questions.map((q) =>
          q.id === question.id ? { ...q, revision: !q.revision } : q,
        ),
      });
    } catch (e) {
      onError((e as Error).message);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="PROJECT DEFENSE"
        title="Prepare to defend it"
        description="Practice questions built from your implementation and documentation gaps."
      />
      <div className="viva-controls">
        <label>
          Examiner perspective
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          >
            {levels.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </label>
        <button className="primary" disabled={busy} onClick={generate}>
          {busy ? "Preparing…" : "Start practice"}
        </button>
      </div>
      {question ? (
        <article className="viva-question">
          <div className="answer-meta">
            <span className="eyebrow">
              QUESTION {index + 1} / {session?.questions.length}
            </span>
            <span className="mono muted">{question.topic}</span>
          </div>
          <h2>{question.question}</h2>
          <button
            className={question.revision ? "secondary selected" : "secondary"}
            onClick={mark}
          >
            <Bookmark size={15} />
            {question.revision ? "Marked for revision" : "Mark for revision"}
          </button>
          <div className="rule" />
          {reveal ? (
            <>
              <h3>Suggested answer</h3>
              <p className="answer-text">{question.answer}</p>
              <h3>Evidence to cite</h3>
              <EvidenceList items={question.evidence} onOpen={onOpen} />
              <div className="limitations">
                <h3>Follow-up question</h3>
                <p>{question.follow_up}</p>
              </div>
            </>
          ) : (
            <button className="reveal" onClick={() => setReveal(true)}>
              <Eye size={18} />
              Reveal suggested answer
            </button>
          )}
          <footer>
            <button
              className="secondary"
              disabled={index === 0}
              onClick={() => move(index - 1)}
            >
              <ChevronLeft size={15} />
              Previous
            </button>
            <span className="muted">
              {session?.questions.filter((q) => q.revision).length} marked for
              revision
            </span>
            <button
              className="secondary"
              disabled={index + 1 === (session?.questions.length ?? 0)}
              onClick={() => move(index + 1)}
            >
              Next
              <ChevronRight size={15} />
            </button>
          </footer>
        </article>
      ) : (
        <div className="practice-empty">
          <div className="eyebrow">FROM SOURCE CODE TO A CLEAR EXPLANATION</div>
          <h2>Know where your answers come from.</h2>
          <p>
            Choose a perspective to practice technology explanations, evidence
            tracing and difficult documentation questions.
          </p>
        </div>
      )}
    </>
  );
}
