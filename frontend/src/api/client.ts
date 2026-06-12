/**
 * Verbatim API client.
 *
 * Talks only to the local Verbatim backend (which in turn talks only to the
 * local Ollama runtime). No third-party calls. In dev, requests to /api are
 * proxied to the FastAPI server (see vite.config.ts).
 */

export const NEEDS_REVIEW = "NEEDS_REVIEW";

export interface CaseInfo {
  id: string;
  name: string;
  documents: string[];
  char_count: number;
}

export interface FieldSpec {
  key: string;
  label: string;
  instruction?: string | null;
  placeholder: string;
}

export interface TemplateInfo {
  id: string;
  name: string;
  filename: string;
  kind: string;
  fields: FieldSpec[];
  style?: string | null;
}

export interface DocText {
  filename: string;
  chars: number;
  text: string;
}

export interface FilledField {
  key: string;
  label: string;
  value: string;
  found: boolean;
  confidence?: number | null;
  source_quote?: string | null;
  source_document?: string | null;
  source_page?: number | null;
  admin_flag?: "correct" | "incorrect" | null;
  review_reason?: string | null;
}

export interface FillResult {
  run_id: string;
  timestamp: string;
  matter_id: string;
  matter_name: string;
  template_id: string;
  template_name: string;
  style?: string | null;
  model: string;
  fields: FilledField[];
  original_text: string;
  filled_text: string;
  inference_seconds: number;
  blanks_total: number;
  blanks_filled: number;
  blanks_needs_review: number;
  retrieval_mode: string;
  status: string;
  message?: string | null;
  raw_model_output?: string | null;
}

export interface OllamaModel {
  name: string;
  size?: number;
  family?: string;
  parameter_size?: string;
  quantization?: string;
  embedding?: boolean;
}

export interface ModelStyleStats {
  model: string;
  style: string;
  runs: number;
  fields_flagged: number;
  fields_correct: number;
  fields_incorrect: number;
  needs_review_fields: number;
  total_fields: number;
  avg_inference_seconds: number;
}

export interface AuthMe {
  authenticated: boolean;
  auth_enabled: boolean;
  username?: string;
  role?: "attorney" | "admin";
}

export interface UserInfo {
  username: string;
  role: "attorney" | "admin";
  disabled: boolean;
  created_at?: string | null;
}

export interface AuditRecord {
  ts: string;
  user: string;
  action: string;
  resource?: string | null;
  ok: boolean;
}

export interface AuditLog {
  intact: boolean;
  broken_at_line: number | null;
  records: AuditRecord[];
}

const BASE = "/api";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // ---- Authentication & access control ----
  me: () => fetch(`${BASE}/auth/me`).then(j<AuthMe>),

  login: (username: string, password: string) =>
    fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }).then(j<{ username: string; role: "attorney" | "admin" }>),

  logout: () => fetch(`${BASE}/auth/logout`, { method: "POST" }).then(j<{ ok: boolean }>),

  users: () => fetch(`${BASE}/auth/users`).then(j<UserInfo[]>),

  createUser: (username: string, password: string, role: "attorney" | "admin") =>
    fetch(`${BASE}/auth/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, role }),
    }).then(j<UserInfo>),

  setUserState: (username: string, disabled: boolean) =>
    fetch(`${BASE}/auth/users/${encodeURIComponent(username)}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disabled }),
    }).then(j<{ ok: boolean }>),

  auditLog: () => fetch(`${BASE}/audit`).then(j<AuditLog>),

  health: () =>
    fetch(`${BASE}/health`).then(
      j<{ ok: boolean; ollama_available: boolean; ollama_host: string }>
    ),

  matters: () => fetch(`${BASE}/matters`).then(j<CaseInfo[]>),

  templates: () => fetch(`${BASE}/templates`).then(j<TemplateInfo[]>),

  matterText: (id: string) =>
    fetch(`${BASE}/matters/${id}/text`).then(j<DocText[]>),

  templateText: (id: string) =>
    fetch(`${BASE}/templates/${id}/text`).then(j<{ text: string }>),

  models: () =>
    fetch(`${BASE}/models`).then(
      j<{ available: boolean; models: OllamaModel[]; message?: string }>
    ),

  fill: (matter_id: string, template_id: string, model: string, signal?: AbortSignal) =>
    fetch(`${BASE}/fill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ matter_id, template_id, model }),
      signal,
    }).then(j<FillResult>),

  runs: () => fetch(`${BASE}/runs`).then(j<FillResult[]>),

  run: (run_id: string) => fetch(`${BASE}/runs/${run_id}`).then(j<FillResult>),

  flag: (run_id: string, field_key: string, flag: "correct" | "incorrect" | null) =>
    fetch(`${BASE}/runs/${run_id}/flag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field_key, flag }),
    }).then(j<FillResult>),

  setStyle: (template_id: string, style: string) =>
    fetch(`${BASE}/templates/${template_id}/style`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style }),
    }).then(j<TemplateInfo>),

  report: () => fetch(`${BASE}/report`).then(j<ModelStyleStats[]>),

  exportUrl: (run_id: string) => `${BASE}/export/${run_id}`,

  // ---- Library: uploads & management ----
  createMatter: (name: string) =>
    fetch(`${BASE}/matters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(j<CaseInfo>),

  uploadDocuments: (matter_id: string, files: FileList | File[]) => {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    return fetch(`${BASE}/matters/${matter_id}/documents`, {
      method: "POST",
      body: fd,
    }).then(j<CaseInfo>);
  },

  deleteDocument: (matter_id: string, filename: string) =>
    fetch(`${BASE}/matters/${matter_id}/documents/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }).then(j<CaseInfo>),

  deleteMatter: (matter_id: string) =>
    fetch(`${BASE}/matters/${matter_id}`, { method: "DELETE" }).then(
      j<{ ok: boolean }>
    ),

  uploadTemplate: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/templates`, { method: "POST", body: fd }).then(
      j<TemplateInfo>
    );
  },

  deleteTemplate: (template_id: string) =>
    fetch(`${BASE}/templates/${template_id}`, { method: "DELETE" }).then(
      j<{ ok: boolean }>
    ),
};
