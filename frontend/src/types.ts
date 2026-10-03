export type ClaimStatus =
  "VERIFIED" | "INFERRED" | "UNVERIFIED" | "CONTRADICTED" | "STALE";
export type Page =
  | "Overview"
  | "Evidence"
  | "Claim Ledger"
  | "Ask Project"
  | "Consistency"
  | "Viva"
  | "Documentation"
  | "Deployment Audit"
  | "Settings";
export interface Evidence {
  id: string;
  file_id: string;
  project_id: string;
  snapshot_id: string;
  commit_sha: string;
  path: string;
  start_line: number;
  end_line: number;
  chunk_type: string;
  content: string;
}
export interface Claim {
  id: string;
  text: string;
  status: ClaimStatus;
  confidence: number;
  explanation: string;
  source_artifact: string;
  source_line: number | null;
  recommendation: string;
  created_at: string;
  snapshot_id: string;
  commit_sha: string;
  evidence: Evidence[];
}
export interface Technology {
  name: string;
  category: string;
  confidence: string;
  status: ClaimStatus;
  basis: string;
  files: string[];
}
export interface Audit {
  name: string;
  status: string;
  detail: string;
}
export interface Summary {
  stack: Technology[];
  file_count: number;
  chunk_count: number;
  claim_counts: Partial<Record<ClaimStatus, number>>;
  languages: Record<string, number>;
  secrets: { path: string; count: number; value: string }[];
  routes: { file: string; method: string; path: string; line: number }[];
  audit: Audit[];
  embedding_model: string;
  limitations: string[];
}
export interface Job {
  id: string;
  snapshot_id: string;
  state: string;
  stage: string;
  error_type: string | null;
  error_summary: string | null;
  created_at: string;
}
export interface Snapshot {
  id: string;
  source_type: string;
  commit_sha: string;
  branch: string | null;
  analyzed_at: string;
  summary: Summary;
}
export interface Project {
  id: string;
  name: string;
  latest_snapshot_id: string | null;
  repository_url: string | null;
}
export interface Overview {
  id: string;
  name: string;
  repository_url: string | null;
  job: Job | null;
  snapshot: Snapshot | null;
  history: {
    id: string;
    commit_sha: string;
    status: string;
    created_at: string;
  }[];
}
export interface SourceFile {
  id: string;
  path: string;
  language: string;
  byte_size: number;
}
export interface FileContent {
  id: string;
  path: string;
  content: string;
  language: string;
  snapshot_id: string;
}
export interface Answer {
  answer: string;
  status: ClaimStatus;
  confidence: number;
  evidence: Evidence[];
  limitations: string[];
  provider: string;
}
export interface Finding {
  id: string;
  kind: string;
  recommendation: string;
  claim: Claim;
}
export interface VivaQuestion {
  id: string;
  question: string;
  answer: string;
  topic: string;
  follow_up: string;
  evidence: Evidence[];
  difficulty: string;
  revision: boolean;
}
export interface VivaSession {
  id: string;
  difficulty: string;
  questions: VivaQuestion[];
}
export interface Doc {
  id: string;
  kind: string;
  content: string;
  snapshot_id: string;
  created_at: string;
}
export interface Auth {
  user: { id: string; email: string };
  csrf: string;
  mode?: string;
  app_env?: string;
}

export const statuses: ClaimStatus[] = [
  "VERIFIED",
  "INFERRED",
  "UNVERIFIED",
  "CONTRADICTED",
  "STALE",
];
