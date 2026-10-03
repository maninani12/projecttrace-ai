import { statuses } from "../types";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  LayoutDashboard,
  Files,
  ListChecks,
  MessageSquareText,
  Columns2,
  GraduationCap,
  FileText,
  ShieldCheck,
  Settings,
  Plus,
  ArrowUpRight,
  Upload,
  GitBranch,
  ChevronRight,
  Menu,
  X,
  Sun,
  Moon,
  LogOut,
  Check,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  FolderGit2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api, post, setCsrf, ApiError } from "../services/api";
import type {
  Auth,
  Overview,
  Project,
  Page,
  Claim,
  Evidence,
  Finding,
} from "../types";
import {
  Empty,
  EvidenceList,
  Loading,
  Logo,
  Modal,
  PageHeading,
  Status,
} from "../components/ui";
import Claims from "../features/claims/Claims";
import Explorer from "../features/evidence/Explorer";
import Ask from "../features/ask/Ask";
import Viva from "../features/viva/Viva";
import Documents from "../features/documents/Documents";

const navigation: [Page, LucideIcon][] = [
  ["Overview", LayoutDashboard],
  ["Evidence", Files],
  ["Claim Ledger", ListChecks],
  ["Ask Project", MessageSquareText],
  ["Consistency", Columns2],
  ["Viva", GraduationCap],
  ["Documentation", FileText],
  ["Deployment Audit", ShieldCheck],
  ["Settings", Settings],
];
const stageNames = [
  "Repository received",
  "Validating files",
  "Filtering sensitive values",
  "Detecting technologies",
  "Building evidence index",
  "Verifying documentation",
  "Analysis complete",
];

export default function App() {
  const [auth, setAuth] = useState<Auth | null>(null),
    [initializing, setInitializing] = useState(true),
    [projects, setProjects] = useState<Project[]>([]),
    [projectId, setProjectId] = useState(""),
    [view, setView] = useState<Overview | null>(null),
    [page, setPage] = useState<Page>("Overview"),
    [snapshotId, setSnapshotId] = useState(""),
    [claims, setClaims] = useState<Claim[]>([]),
    [claimTotal, setClaimTotal] = useState(0),
    [findings, setFindings] = useState<Finding[]>([]),
    [focus, setFocus] = useState<Evidence | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [modal, setModal] = useState(false),
    [mobile, setMobile] = useState(false),
    [theme, setTheme] = useState(
      () => localStorage.getItem("pt-theme") ?? "dark",
    ),
    [demoAvailable, setDemoAvailable] = useState(false),
    [authForm, setAuthForm] = useState<"login" | "register">("login"),
    [loginBusy, setLoginBusy] = useState(false);
  const onError = useCallback((message: string) => setError(message), []);
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 760px)").matches,
  );
  const requestSequence = useRef(0);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const change = () => {
      setNarrow(media.matches);
      if (!media.matches) setMobile(false);
    };
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (!mobile) return;
    const previous = document.activeElement as HTMLElement | null;
    const sidebar = document.querySelector<HTMLElement>(".sidebar.open");
    sidebar?.querySelector<HTMLElement>('button[aria-current="page"]')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobile(false);
      if (event.key === "Tab") {
        const items = sidebar?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), select, a[href]",
        );
        if (!items?.length) return;
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      if (previous?.isConnected) previous.focus();
    };
  }, [mobile]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("pt-theme", theme);
  }, [theme]);
  useEffect(() => {
    api<Auth>("/auth/me")
      .then((a) => {
        setCsrf(a.csrf);
        setAuth(a);
      })
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) onError(e.message);
      })
      .finally(() => setInitializing(false));
    fetch("/health")
      .then((r) => r.json())
      .then((d) => setDemoAvailable(Boolean(d.demo_available)))
      .catch(() => {});
  }, [onError]);
  const loadProjects = useCallback(async () => {
    const result = await api<{ items: Project[] }>("/projects");
    setProjects(result.items);
    setProjectId((id) => id || result.items[0]?.id || "");
  }, []);
  useEffect(() => {
    if (auth) void loadProjects().catch((e) => onError(e.message));
  }, [auth, loadProjects, onError]);
  const reload = useCallback(async () => {
    if (!projectId) return;
    const sequence = ++requestSequence.current;
    const detail = await api<Overview>(
      `/projects/${projectId}${snapshotId ? "?snapshot_id=" + snapshotId : ""}`,
    );
    if (sequence !== requestSequence.current) return;
    setView(detail);
    if (detail.snapshot) {
      const suffix = "?snapshot_id=" + detail.snapshot.id;
      const [ledger, consistency] = await Promise.all([
        api<{ items: Claim[]; total: number }>(
          `/projects/${projectId}/claims${suffix}`,
        ),
        api<{ items: Finding[] }>(
          `/projects/${projectId}/consistency${suffix}`,
        ),
      ]);
      if (sequence !== requestSequence.current) return;
      setClaims(ledger.items);
      setClaimTotal(ledger.total);
      setFindings(consistency.items);
    } else {
      setClaims([]);
      setFindings([]);
    }
  }, [projectId, snapshotId]);
  useEffect(() => {
    if (!projectId) {
      setView(null);
      return;
    }
    setBusy(true);
    setView(null);
    void reload()
      .catch((e) => onError(e.message))
      .finally(() => setBusy(false));
  }, [projectId, reload, onError]);
  const jobActive =
    view?.job && ["QUEUED", "PROCESSING"].includes(view.job.state);
  useEffect(() => {
    if (!jobActive) return;
    let live = true;
    const timer = setInterval(() => {
      api<Overview>(`/projects/${projectId}`)
        .then((d) => {
          if (live) {
            setView(d);
            if (d.job && !["QUEUED", "PROCESSING"].includes(d.job.state)) {
              void reload().catch((e) => onError(e.message));
              void loadProjects();
            }
          }
        })
        .catch((e) => onError(e.message));
    }, 1500);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [jobActive, projectId, reload, loadProjects, onError]);
  const openEvidence = (e: Evidence) => {
    setFocus(e);
    setPage("Evidence");
    setMobile(false);
  };
  const switchProject = (id: string) => {
    setSnapshotId("");
    setProjectId(id);
    setPage("Overview");
    setFocus(null);
    setError("");
  };
  const closeModal = useCallback(() => setModal(false), []);
  const demo = async () => {
    setLoginBusy(true);
    setError("");
    try {
      const a = await post<Auth>("/auth/demo");
      setCsrf(a.csrf);
      const p = await post<Project>("/projects", {
        name: "Complaint workspace",
      });
      await post(`/projects/${p.id}/demo`);
      setProjectId(p.id);
      setAuth(a);
      await loadProjects();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setLoginBusy(false);
    }
  };
  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginBusy(true);
    setError("");
    const values = new FormData(event.currentTarget);
    try {
      const a = await post<Auth>("/auth/" + authForm, {
        email: values.get("email"),
        password: values.get("password"),
      });
      setCsrf(a.csrf);
      setAuth(a);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setLoginBusy(false);
    }
  };
  const logout = async () => {
    try {
      await post("/auth/logout");
      setAuth(null);
      setProjects([]);
      setProjectId("");
      setView(null);
      setCsrf("");
    } catch (e) {
      onError((e as Error).message);
    }
  };
  const retry = async () => {
    if (!projectId) return;
    try {
      await post(`/projects/${projectId}/analyze`);
      setSnapshotId("");
      await reload();
    } catch (e) {
      onError((e as Error).message);
    }
  };
  const cancelQueued = async () => {
    try {
      await post(`/projects/${projectId}/cancel`);
      await reload();
    } catch (e) {
      onError((e as Error).message);
    }
  };
  const moreClaims = async () => {
    try {
      const d = await api<{ items: Claim[]; total: number }>(
        `/projects/${projectId}/claims?snapshot_id=${view?.snapshot?.id}&offset=${claims.length}`,
      );
      setClaims([...claims, ...d.items]);
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const loadClaimPage = useCallback(
    async (
      status: import("../types").ClaimStatus | "ALL",
      query: string,
      offset: number,
    ) => {
      const params = new URLSearchParams({
        snapshot_id: view?.snapshot?.id ?? "",
        q: query,
        offset: String(offset),
      });
      if (status !== "ALL") params.set("status", status);
      return api<{ items: Claim[]; total: number }>(
        `/projects/${projectId}/claims?${params}`,
      );
    },
    [projectId, view?.snapshot?.id],
  );

  if (initializing)
    return (
      <div className="boot">
        <Logo />
        <Loading />
      </div>
    );
  if (!auth)
    return (
      <div className="landing">
        <header className="landing-header">
          <a className="brand" href="#">
            <Logo />
            <span>
              ProjectTrace <b>AI</b>
            </span>
          </a>
          <span className="mono muted">EVIDENCE BEFORE GENERATION</span>
          <button
            className="icon-btn"
            aria-label="Toggle color theme"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>
        <main className="landing-main">
          <section className="landing-copy">
            <div className="eyebrow">
              <span className="live-dot" /> PROJECT INTELLIGENCE, GROUNDED IN
              SOURCE
            </div>
            <h1>
              Understand it.
              <br />
              Verify it.
              <br />
              Document it.
              <br />
              <span>Defend it.</span>
            </h1>
            <p>
              Trace your project’s claims back to the code.
              <br />
              Build documentation and viva answers you can substantiate.
            </p>
            <div className="landing-actions">
              <button
                className="primary"
                onClick={() => document.getElementById("email")?.focus()}
              >
                Analyze a project
                <ArrowUpRight size={16} />
              </button>
              {demoAvailable && (
                <button
                  className="secondary"
                  disabled={loginBusy}
                  onClick={demo}
                >
                  {loginBusy ? "Opening demo…" : "View demo"}
                  <ArrowRight size={16} />
                </button>
              )}
            </div>
            <div className="landing-proof">
              <div>
                <Check size={17} />
                <span>Source provenance</span>
              </div>
              <div>
                <Columns2 size={17} />
                <span>Documentation consistency</span>
              </div>
              <div>
                <GraduationCap size={17} />
                <span>Evidence-based viva</span>
              </div>
            </div>
          </section>
          <section className="landing-right">
            <div className="sample-ledger">
              <header>
                <ListChecks size={16} />
                <span>Claim ledger</span>
                <span className="mono muted">SAMPLE SCENARIO</span>
              </header>
              <p>“The project uses MongoDB.”</p>
              <Status value="CONTRADICTED" />
              <div className="sample-evidence">
                <div className="mono muted">backend/database.py · L4</div>
                <code>
                  DATABASE_URL = <span>“postgresql://…”</span>
                </code>
              </div>
              <footer>
                <GitBranch size={14} />
                README claim → source evidence
              </footer>
            </div>
            <form className="auth-form" onSubmit={login}>
              <h2>
                {authForm === "login"
                  ? "Open your workspace"
                  : "Create your workspace"}
              </h2>
              <p>Private project evidence, scoped to your account.</p>
              <label className="field" htmlFor="email">
                Email
                <input
                  id="email"
                  type="email"
                  name="email"
                  required
                  autoComplete="email"
                  placeholder="you@example.com"
                />
              </label>
              <label className="field" htmlFor="password">
                Password
                <input
                  id="password"
                  type="password"
                  name="password"
                  minLength={12}
                  maxLength={128}
                  required
                  autoComplete={
                    authForm === "login" ? "current-password" : "new-password"
                  }
                  placeholder="At least 12 characters"
                />
              </label>
              {error && (
                <div role="alert" className="error-inline">
                  {error}
                </div>
              )}
              <button className="primary" disabled={loginBusy}>
                {loginBusy
                  ? "Opening…"
                  : authForm === "login"
                    ? "Sign in"
                    : "Create account"}
                <ArrowRight size={16} />
              </button>
              <button
                type="button"
                className="text-btn"
                onClick={() =>
                  setAuthForm(authForm === "login" ? "register" : "login")
                }
              >
                {authForm === "login"
                  ? "New here? Create an account"
                  : "Already have an account? Sign in"}
              </button>
            </form>
          </section>
        </main>
        <footer className="landing-footer">
          For students and developers who want their project story to match the
          implementation.
          <span>Static analysis. No uploaded code execution.</span>
        </footer>
      </div>
    );

  const snapshot = view?.snapshot,
    summary = snapshot?.summary;
  const navigate = (target: Page) => {
    setPage(target);
    setMobile(false);
  };
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      {mobile && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        className={"sidebar " + (mobile ? "open" : "")}
        inert={narrow && !mobile}
        role={mobile ? "dialog" : undefined}
        aria-modal={mobile ? true : undefined}
        aria-label={mobile ? "Project navigation menu" : undefined}
      >
        <div className="brand">
          <Logo />
          <span>
            ProjectTrace <b>AI</b>
          </span>
        </div>
        <div className="workspace-label eyebrow">WORKSPACE</div>
        <label className="sr-only" htmlFor="project-switcher">
          Current project
        </label>
        <div className="project-switcher">
          <FolderGit2 size={16} />
          <select
            id="project-switcher"
            value={projectId}
            onChange={(e) => switchProject(e.target.value)}
          >
            {!projects.length && <option value="">No projects yet</option>}
            {projects.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <nav aria-label="Project navigation">
          {navigation.map(([name, Icon], i) => (
            <button
              key={name}
              aria-current={page === name ? "page" : undefined}
              className={
                (page === name ? "active " : "") +
                (i === 5 ? "nav-divider" : "")
              }
              onClick={() => navigate(name)}
            >
              <Icon size={17} />
              {name}
              {name === "Consistency" &&
                !!summary?.claim_counts.CONTRADICTED && (
                  <span className="nav-count">
                    {summary.claim_counts.CONTRADICTED}
                  </span>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <ShieldCheck size={16} />
            <span>
              Evidence stays private.
              <small>Repositories are analyzed as data.</small>
            </span>
          </div>
          <div className="user-row">
            <span className="avatar">
              {auth.user.email.charAt(0).toUpperCase()}
            </span>
            <div>
              <strong>
                {auth.user.email.startsWith("demo-")
                  ? "Local demo"
                  : auth.user.email.split("@")[0]}
              </strong>
              <small>
                {auth.mode === "openai"
                  ? "AI provider enabled"
                  : "Static evidence mode"}
              </small>
            </div>
            <button
              className="icon-btn"
              aria-label="Toggle color theme"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button className="icon-btn" aria-label="Sign out" onClick={logout}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace" inert={mobile}>
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-btn mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span className="muted">Projects</span>
            <ChevronRight size={13} />
            <strong>{view?.name ?? "Workspace"}</strong>
          </div>
          <div className="topbar-meta">
            {snapshot && (
              <>
                <span className="mono branch">
                  <GitBranch size={13} />
                  {snapshot.branch ?? "ZIP snapshot"}
                </span>
                <span className="mono muted commit">
                  {snapshot.commit_sha.slice(0, 8)}
                </span>
              </>
            )}
            <span
              className={"analysis-indicator " + (jobActive ? "working" : "")}
            >
              <span className="live-dot" />
              {jobActive
                ? "Analyzing"
                : snapshot
                  ? "Analysis complete"
                  : "Awaiting import"}
            </span>
            <button
              className="secondary compact"
              onClick={() => setModal(true)}
            >
              <Plus size={14} />
              Analyze project
            </button>
          </div>
        </header>
        <main
          id="main-content"
          className={"main-content " + (page === "Evidence" ? "wide" : "")}
        >
          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button
                className="icon-btn"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={17} />
              </button>
            </div>
          )}
          {view?.job?.state === "FAILED" && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={18} />
              <span>{view.job.error_summary}</span>
              <button className="secondary" onClick={retry}>
                Retry analysis
              </button>
            </div>
          )}
          {jobActive && (
            <div className="job-progress" role="status">
              <div>
                <span className="spinner" />
                <strong>{view?.job?.stage}</strong>
                {view?.job?.state === "QUEUED" && (
                  <button className="text-btn" onClick={cancelQueued}>
                    Cancel queued analysis
                  </button>
                )}
                <span className="muted">
                  You can continue inspecting the previous snapshot.
                </span>
              </div>
              <ol>
                {stageNames.map((s, i) => {
                  const stage = Math.max(
                    stageNames.indexOf(view?.job?.stage ?? ""),
                    1,
                  );
                  return (
                    <li
                      className={
                        i < stage ? "done" : i === stage ? "current" : ""
                      }
                      key={s}
                    >
                      {i < stage ? (
                        <Check size={12} />
                      ) : (
                        <span className="step-dot" />
                      )}
                      {s}
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
          {busy ? (
            <Loading />
          ) : page === "Settings" ? (
            <WorkspaceSettings
              project={view}
              auth={auth}
              onError={onError}
              onDelete={() => {
                setProjectId("");
                setSnapshotId("");
                void loadProjects();
              }}
            />
          ) : !snapshot ? (
            <Empty
              title={
                projectId
                  ? "Your project needs evidence."
                  : "Start with your implementation."
              }
              action={
                <button className="primary" onClick={() => setModal(true)}>
                  <Upload size={16} />
                  Import a project
                </button>
              }
            >
              Upload a ZIP or import a public GitHub repository. ProjectTrace
              will index the source, compare claims, and prepare evidence you
              can defend.
            </Empty>
          ) : (
            <>
              {(view?.history.filter((h) => h.status === "COMPLETED").length ??
                0) > 1 && (
                <div className="snapshot-selector">
                  <label>
                    Analyzed snapshot
                    <select
                      value={snapshotId || snapshot.id}
                      onChange={(e) => setSnapshotId(e.target.value)}
                    >
                      {view?.history
                        .filter((h) => h.status === "COMPLETED")
                        .map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.commit_sha.slice(0, 8)} ·{" "}
                            {new Date(h.created_at).toLocaleString()}
                          </option>
                        ))}
                    </select>
                  </label>
                  <span className="muted small">
                    Viva and documentation generation use the latest completed
                    snapshot.
                  </span>
                </div>
              )}
              {page === "Overview" && (
                <>
                  <PageHeading
                    eyebrow="PROJECT OVERVIEW"
                    title={view?.name ?? ""}
                    description="A clear view of what your project implements—and what still needs evidence."
                  >
                    <button
                      className="secondary"
                      disabled={Boolean(jobActive)}
                      onClick={retry}
                    >
                      <RefreshCw size={14} />
                      Reanalyze
                    </button>
                    <button
                      className="primary"
                      onClick={() => navigate("Claim Ledger")}
                    >
                      Review claims
                      <ArrowUpRight size={15} />
                    </button>
                  </PageHeading>
                  <div className="snapshot-line">
                    <span>
                      <GitBranch size={14} />
                      {snapshot.branch ??
                        snapshot.source_type.toUpperCase() + " IMPORT"}
                    </span>
                    <span className="mono">
                      {snapshot.commit_sha.slice(0, 12)}
                    </span>
                    <span>
                      Analyzed {new Date(snapshot.analyzed_at).toLocaleString()}
                    </span>
                    {view?.repository_url && (
                      <a
                        href={view.repository_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Repository
                        <ArrowUpRight size={12} />
                      </a>
                    )}
                  </div>
                  <section className="health-strip" aria-label="Claim health">
                    {statuses.map((s) => (
                      <button key={s} onClick={() => navigate("Claim Ledger")}>
                        <Status value={s} />
                        <strong>{summary?.claim_counts[s] ?? 0}</strong>
                        <small>
                          {s === "VERIFIED"
                            ? "Direct source evidence"
                            : s === "INFERRED"
                              ? "Indirect support"
                              : s === "UNVERIFIED"
                                ? "Needs more evidence"
                                : s === "CONTRADICTED"
                                  ? "Conflicting evidence"
                                  : "Changed since last snapshot"}
                        </small>
                      </button>
                    ))}
                  </section>
                  <div className="overview-columns">
                    <section className="review-section">
                      <header className="section-header">
                        <div>
                          <div className="eyebrow">
                            DOCUMENTATION CONSISTENCY
                          </div>
                          <h2>Claims that need your attention</h2>
                        </div>
                        <button
                          className="text-btn"
                          onClick={() => navigate("Consistency")}
                        >
                          Review all
                          <ArrowUpRight size={14} />
                        </button>
                      </header>
                      {findings
                        .filter((f) => f.kind !== "MATCH")
                        .slice(0, 4)
                        .map((f) => (
                          <button
                            className="review-row"
                            key={f.id}
                            onClick={() => navigate("Consistency")}
                          >
                            <div>
                              <Status value={f.claim.status} />
                              <h3>{f.claim.text}</h3>
                              <p>{f.claim.recommendation}</p>
                              <span className="mono muted">
                                {f.claim.source_artifact}
                                {f.claim.source_line &&
                                  ":" + f.claim.source_line}
                              </span>
                            </div>
                            <ChevronRight size={18} />
                          </button>
                        ))}
                      {!findings.length && (
                        <p className="muted">
                          No technical README claims were detected. Review
                          coverage before relying on this result.
                        </p>
                      )}
                      <div className="overview-ask">
                        <MessageSquareText size={21} />
                        <div>
                          <h3>Follow a question to its source.</h3>
                          <p>
                            Ask about the database, backend or implementation.
                          </p>
                        </div>
                        <button
                          className="secondary"
                          onClick={() => navigate("Ask Project")}
                        >
                          Ask project
                          <ArrowRight size={14} />
                        </button>
                      </div>
                    </section>
                    <aside className="stack-section">
                      <div className="eyebrow">DETECTED IMPLEMENTATION</div>
                      <h2>Technology stack</h2>
                      {summary?.stack.map((t) => (
                        <div className="stack-row" key={t.name}>
                          <div className="tech-initial">
                            {t.name.slice(0, 2)}
                          </div>
                          <div>
                            <strong>{t.name}</strong>
                            <span>{t.category}</span>
                          </div>
                          <span className="mono muted">{t.confidence}</span>
                        </div>
                      ))}
                      <p className="small muted">
                        Detected from source usage, configuration and manifests.
                        Dependency-only signals are inferred.
                      </p>
                      <div className="rule" />
                      <h3>Repository index</h3>
                      <dl className="index-stats">
                        <div>
                          <dt>Analyzed files</dt>
                          <dd>{summary?.file_count}</dd>
                        </div>
                        <div>
                          <dt>Evidence chunks</dt>
                          <dd>{summary?.chunk_count}</dd>
                        </div>
                        <div>
                          <dt>Routes detected</dt>
                          <dd>{summary?.routes.length}</dd>
                        </div>
                        <div>
                          <dt>Secret findings</dt>
                          <dd>{summary?.secrets.length}</dd>
                        </div>
                      </dl>
                      <button
                        className="text-btn"
                        onClick={() => navigate("Evidence")}
                      >
                        Explore source evidence
                        <ArrowUpRight size={14} />
                      </button>
                    </aside>
                  </div>
                  <div className="scope-note">
                    <ShieldCheck size={17} />
                    <p>
                      Static inspection only. Source presence does not establish
                      successful execution, test results or deployment.
                    </p>
                  </div>
                </>
              )}
              {page === "Claim Ledger" && (
                <Claims
                  claims={claims}
                  total={claimTotal}
                  onMore={moreClaims}
                  loadPage={loadClaimPage}
                  counts={summary?.claim_counts}
                  onOpen={openEvidence}
                />
              )}{" "}
              {page === "Evidence" && (
                <Explorer
                  key={snapshot.id}
                  projectId={projectId}
                  snapshotId={snapshot.id}
                  focus={focus?.snapshot_id === snapshot.id ? focus : null}
                  onError={onError}
                />
              )}{" "}
              {page === "Ask Project" && (
                <Ask
                  key={snapshot.id}
                  projectId={projectId}
                  snapshotId={snapshot.id}
                  onOpen={openEvidence}
                  onError={onError}
                />
              )}{" "}
              {page === "Consistency" && (
                <>
                  <PageHeading
                    eyebrow="CROSS-ARTIFACT REVIEW"
                    title="Does the story match the source?"
                    description="Compare documentation statements against the analyzed implementation."
                  />
                  <div className="comparison-header">
                    <span>Documentation claim</span>
                    <span>Repository evidence</span>
                  </div>
                  {findings.map((f) => (
                    <article className="comparison" key={f.id}>
                      <header>
                        <Status value={f.claim.status} />
                        <span className="mono muted">
                          {f.claim.source_artifact} · L
                          {f.claim.source_line ?? "?"}
                        </span>
                        <span className="mono muted">{f.kind}</span>
                      </header>
                      <div className="comparison-body">
                        <div>
                          <h2>“{f.claim.text}”</h2>
                          <p>{f.claim.explanation}</p>
                        </div>
                        <div>
                          <EvidenceList
                            items={f.claim.evidence.filter(
                              (e) => e.path !== f.claim.source_artifact,
                            )}
                            onOpen={openEvidence}
                          />
                          {f.claim.evidence.filter(
                            (e) => e.path !== f.claim.source_artifact,
                          ).length === 0 && (
                            <p className="muted">
                              No independent implementation excerpt supports
                              this claim.
                            </p>
                          )}
                        </div>
                      </div>
                      <footer>
                        <span className="eyebrow">RECOMMENDATION</span>
                        <p>{f.recommendation}</p>
                      </footer>
                    </article>
                  ))}
                  {!findings.length && (
                    <Empty title="No comparison candidates found.">
                      Technical README claims may be absent or outside the
                      current heuristic rules.
                    </Empty>
                  )}
                </>
              )}
              {page === "Viva" && (
                <Viva
                  key={projectId}
                  projectId={projectId}
                  onOpen={openEvidence}
                  onError={onError}
                />
              )}{" "}
              {page === "Documentation" && (
                <Documents
                  key={projectId}
                  projectId={projectId}
                  onError={onError}
                />
              )}{" "}
              {page === "Deployment Audit" && (
                <>
                  <PageHeading
                    eyebrow="STATIC PROJECT HEALTH"
                    title="Deployment readiness audit"
                    description="Check configuration indicators before planning a deployment."
                  />
                  <div className="audit-summary">
                    <ShieldCheck size={27} />
                    <div>
                      <h2>Presence is a starting point.</h2>
                      <p>
                        This audit inspects files and configuration. It does not
                        run the project, tests, or deployment commands.
                      </p>
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Check</th>
                          <th>Result</th>
                          <th>Inspection notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary?.audit.map((c) => (
                          <tr key={c.name}>
                            <td>
                              <strong>{c.name}</strong>
                            </td>
                            <td>
                              <span
                                className={
                                  "audit-status " +
                                  c.status.toLowerCase().replaceAll(" ", "-")
                                }
                              >
                                {c.status === "PASS" ? (
                                  <Check size={13} />
                                ) : (
                                  <AlertTriangle size={13} />
                                )}{" "}
                                {c.status}
                              </span>
                            </td>
                            <td className="muted">{c.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!!summary?.secrets.length && (
                    <section className="secret-findings">
                      <h2>Potential secrets</h2>
                      {summary.secrets.map((s) => (
                        <p key={s.path}>
                          <span className="mono">{s.path}</span>
                          <Status value="UNVERIFIED" />
                          <span className="mono">REDACTED</span>
                        </p>
                      ))}
                    </section>
                  )}
                </>
              )}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>ProjectTrace AI</span>
          <span className="mono">PROVENANCE · VERIFICATION · TRACEABILITY</span>
        </footer>
      </div>
      {modal && (
        <ImportModal
          currentProject={view}
          onClose={closeModal}
          onError={onError}
          onDone={async (id) => {
            closeModal();
            switchProject(id);
            await loadProjects();
            if (id === projectId) await reload();
          }}
        />
      )}
    </div>
  );
}

function ImportModal({
  currentProject,
  onClose,
  onDone,
  onError,
}: {
  currentProject: Overview | null;
  onClose: () => void;
  onDone: (id: string) => Promise<void>;
  onError: (s: string) => void;
}) {
  const [tab, setTab] = useState<"zip" | "github" | "demo">("zip"),
    [name, setName] = useState(""),
    [url, setUrl] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [existing, setExisting] = useState(false),
    [busy, setBusy] = useState(false),
    [localError, setLocalError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setLocalError("");
    let id = "";
    try {
      id =
        existing && currentProject
          ? currentProject.id
          : (
              await post<Project>("/projects", {
                name: name || "Demo workspace",
              })
            ).id;
      if (tab === "zip") {
        if (!file) throw new Error("Choose a ZIP file first.");
        const data = new FormData();
        data.append("file", file);
        await api(`/projects/${id}/upload`, { method: "POST", body: data });
      } else if (tab === "github")
        await post(`/projects/${id}/github`, { url });
      else await post(`/projects/${id}/demo`);
      await onDone(id);
    } catch (e) {
      const message = (e as Error).message;
      setLocalError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Analyze a project" onClose={busy ? () => {} : onClose}>
      <p className="muted">
        Import source evidence. Your repository is parsed as data and never
        executed.
      </p>
      <div className="import-tabs" role="group" aria-label="Import method">
        {(["zip", "github", "demo"] as const).map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t === "zip"
              ? "ZIP archive"
              : t === "github"
                ? "GitHub repository"
                : "Sample project"}
          </button>
        ))}
      </div>
      <form onSubmit={submit}>
        {currentProject && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={existing}
              onChange={(e) => setExisting(e.target.checked)}
            />
            Add a snapshot to {currentProject.name}
          </label>
        )}
        {!existing && (
          <label className="field">
            Project name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required={tab !== "demo"}
              maxLength={120}
              placeholder={
                tab === "demo"
                  ? "Demo workspace"
                  : "e.g. Campus complaint portal"
              }
            />
          </label>
        )}
        {tab === "zip" && (
          <label className="upload-zone">
            <Upload size={28} />
            <strong>{file ? file.name : "Choose a repository ZIP"}</strong>
            <span>Up to 50 MB by default · UTF-8 source files</span>
            <input
              type="file"
              accept=".zip,application/zip"
              aria-label="Repository ZIP"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        )}
        {tab === "github" && (
          <label className="field">
            Public repository URL
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
            />
            <span className="small muted">
              The default branch is resolved to an exact commit before download.
            </span>
          </label>
        )}
        {tab === "demo" && (
          <div className="demo-note">
            <FolderGit2 size={24} />
            <h3>Complaint workspace</h3>
            <p>
              A safe React + FastAPI sample configured for PostgreSQL. Its
              README intentionally claims MongoDB to demonstrate a
              contradiction.
            </p>
          </div>
        )}
        {localError && (
          <p role="alert" className="error-inline">
            {localError}
          </p>
        )}
        <div className="modal-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Importing…" : "Start analysis"}
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
    </Modal>
  );
}

function WorkspaceSettings({
  project,
  auth,
  onError,
  onDelete,
}: {
  project: Overview | null;
  auth: Auth;
  onError: (s: string) => void;
  onDelete: () => void;
}) {
  const [confirmation, setConfirmation] = useState(""),
    [busy, setBusy] = useState(false);
  const remove = async (event: FormEvent) => {
    event.preventDefault();
    if (!project) return;
    setBusy(true);
    try {
      await api(`/projects/${project.id}`, {
        method: "DELETE",
        body: JSON.stringify({ confirmation }),
      });
      onDelete();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE"
        title="Settings & privacy"
        description="Understand how your project evidence is stored and processed."
      />
      <section className="settings-section">
        <h2>Evidence handling</h2>
        <dl>
          <div>
            <dt>Account</dt>
            <dd>{auth.user.email}</dd>
          </div>
          <div>
            <dt>Generation provider</dt>
            <dd>{auth.mode ?? "offline"}</dd>
          </div>
          <div>
            <dt>Source execution</dt>
            <dd>Prohibited. Static analysis only.</dd>
          </div>
          <div>
            <dt>Secret handling</dt>
            <dd>
              Likely credentials are redacted before evidence storage and
              provider transmission. Detection is heuristic.
            </dd>
          </div>
          <div>
            <dt>Retention</dt>
            <dd>
              Original ZIP retention defaults to 24 hours; terminal uploads are
              removed by worker maintenance. Derived evidence stays until
              project deletion.
            </dd>
          </div>
          <div>
            <dt>External AI</dt>
            <dd>
              When OpenAI is enabled, up to six trimmed retrieved excerpts and
              your question are sent to the provider. Offline mode sends no
              project content to an AI provider.
            </dd>
          </div>
          <div>
            <dt>Embedding mode</dt>
            <dd>
              {project?.snapshot?.summary.embedding_model ??
                "Configured by the administrator"}
              ; hashing-v1 uses lexical vectors.
            </dd>
          </div>
        </dl>
      </section>
      {project && (
        <section className="settings-section danger-zone">
          <h2>Delete this project</h2>
          <p>
            Deletes snapshots, source evidence, claims, generated documents,
            viva sessions and retained uploads. This cannot be undone.
          </p>
          <form onSubmit={remove}>
            <label className="field">
              Type “{project.name}” to confirm
              <input
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                placeholder={project.name}
              />
            </label>
            <button
              className="danger"
              disabled={
                busy ||
                confirmation !== project.name ||
                ["QUEUED", "PROCESSING"].includes(project.job?.state ?? "")
              }
            >
              Delete project and its evidence
            </button>
          </form>
        </section>
      )}
    </>
  );
}
