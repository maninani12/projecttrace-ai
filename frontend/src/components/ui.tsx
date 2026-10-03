import { useEffect, useRef, type ReactNode } from "react";
import {
  X,
  Check,
  GitBranch,
  AlertTriangle,
  HelpCircle,
  Clock,
  ArrowUpRight,
} from "lucide-react";
import type { ClaimStatus, Evidence } from "../types";
const stateIcons = {
  VERIFIED: Check,
  INFERRED: GitBranch,
  UNVERIFIED: HelpCircle,
  CONTRADICTED: AlertTriangle,
  STALE: Clock,
};
export function Status({ value }: { value: string }) {
  const Icon = stateIcons[value as ClaimStatus] ?? HelpCircle;
  return (
    <span className={"status " + value.toLowerCase()}>
      <Icon size={12} />
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function Logo() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" width="30" height="30">
      <rect width="32" height="32" rx="8" fill="var(--accent-dim)" />
      <path
        d="M8 22V9h9v7h7M13 19l4 4 8-9"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-symbol">
        <GitBranch size={30} />
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      Loading evidence…
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.querySelector<HTMLElement>("button,input,select")?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const items = dialog?.querySelectorAll<HTMLElement>(
          "button:not([disabled]),input,select,textarea,a[href]",
        );
        if (items?.length) {
          const first = items[0],
            last = items[items.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-overlay">
      <div
        ref={ref}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-btn"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
export function EvidenceList({
  items,
  onOpen,
}: {
  items: Evidence[];
  onOpen: (item: Evidence) => void;
}) {
  return (
    <div className="evidence-list">
      {items.map((e) => (
        <details key={e.id}>
          <summary>
            <span className="mono">{e.path}</span>
            <span className="muted mono">
              L{e.start_line}–{e.end_line}
            </span>
          </summary>
          <pre tabIndex={0} aria-label="Source excerpt">
            {e.content}
          </pre>
          <button className="text-btn" onClick={() => onOpen(e)}>
            Open source <ArrowUpRight size={14} />
          </button>
        </details>
      ))}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children && <div className="heading-actions">{children}</div>}
    </div>
  );
}
