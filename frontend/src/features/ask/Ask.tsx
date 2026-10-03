import { useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import type { Answer, Evidence } from "../../types";
import { post } from "../../services/api";
import { EvidenceList, PageHeading, Status } from "../../components/ui";
const suggestions = [
  "Which database does this project use?",
  "What backend framework does this project use?",
  "How does authentication work?",
];
export default function Ask({
  projectId,
  snapshotId,
  onOpen,
  onError,
}: {
  projectId: string;
  snapshotId: string;
  onOpen: (e: Evidence) => void;
  onError: (s: string) => void;
}) {
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<Answer | null>(null),
    [busy, setBusy] = useState(false);
  const submit = async (value = question) => {
    if (value.trim().length < 3) return;
    setQuestion(value);
    setBusy(true);
    setAnswer(null);
    try {
      setAnswer(
        await post<Answer>(`/projects/${projectId}/ask`, {
          question: value,
          snapshot_id: snapshotId,
        }),
      );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="PROJECT INTELLIGENCE"
        title="Ask your project"
        description="Ask a precise question. Start with the implementation, follow the evidence."
      />
      <form
        className="question-form"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Search size={22} />
        <label className="sr-only" htmlFor="project-question">
          Project question
        </label>
        <textarea
          id="project-question"
          rows={2}
          maxLength={2000}
          placeholder="What would you like to verify?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          required
          minLength={3}
        />
        <button
          className="primary"
          disabled={busy || question.trim().length < 3}
        >
          {busy ? "Retrieving…" : "Ask project"}
          <ArrowUpRight size={16} />
        </button>
      </form>
      <div className="suggestions">
        {suggestions.map((s) => (
          <button disabled={busy} key={s} onClick={() => void submit(s)}>
            {s}
            <ArrowUpRight size={13} />
          </button>
        ))}
      </div>
      {answer ? (
        <article className="answer">
          <div className="answer-meta">
            <Status value={answer.status} />
            <span className="mono muted">
              Confidence {Math.round(answer.confidence * 100)}% ·{" "}
              {answer.provider === "offline"
                ? "static evidence mode"
                : "AI summary"}
            </span>
          </div>
          <h2>What the evidence shows</h2>
          <p className="answer-text">{answer.answer}</p>
          <h3>Supporting evidence</h3>
          <EvidenceList items={answer.evidence} onOpen={onOpen} />
          <div className="limitations">
            <h3>Limits of this answer</h3>
            {answer.limitations.map((x) => (
              <p key={x}>{x}</p>
            ))}
          </div>
        </article>
      ) : (
        <div className="qa-guidance">
          <div className="eyebrow">A GOOD QUESTION HAS A TRACEABLE ANSWER</div>
          <div className="guidance-columns">
            <div>
              <h3>Implementation</h3>
              <p>Locate frameworks, configuration, routes and data access.</p>
            </div>
            <div>
              <h3>Verification</h3>
              <p>Check whether your documentation matches the source.</p>
            </div>
            <div>
              <h3>Uncertainty</h3>
              <p>
                Missing evidence is identified explicitly, never filled with
                invented behavior.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
