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

const BASE = "/api";

// ---- Optional bearer-token auth (matches VERBATIM_API_TOKEN on the backend) ----
const TOKEN_KEY = "verbatim_api_token";

export function setApiToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getApiToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/** fetch() with the Authorization header attached when a token is stored. */
function request(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getApiToken();
  if (token) {
    init.headers = { ...(init.headers as Record<string, string>), Authorization: `Bearer ${token}` };
  }
  return fetch(input, init);
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    request(`${BASE}/health`).then(
      j<{ ok: boolean; ollama_available: boolean; ollama_host: string }>
    ),

  matters: () => request(`${BASE}/matters`).then(j<CaseInfo[]>),

  templates: () => request(`${BASE}/templates`).then(j<TemplateInfo[]>),

  matterText: (id: string) =>
    request(`${BASE}/matters/${id}/text`).then(j<DocText[]>),

  templateText: (id: string) =>
    request(`${BASE}/templates/${id}/text`).then(j<{ text: string }>),

  models: () =>
    request(`${BASE}/models`).then(
      j<{ available: boolean; models: OllamaModel[]; message?: string }>
    ),

  fill: (matter_id: string, template_id: string, model: string, signal?: AbortSignal) =>
    request(`${BASE}/fill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ matter_id, template_id, model }),
      signal,
    }).then(j<FillResult>),

  runs: () => request(`${BASE}/runs`).then(j<FillResult[]>),

  run: (run_id: string) => request(`${BASE}/runs/${run_id}`).then(j<FillResult>),

  flag: (run_id: string, field_key: string, flag: "correct" | "incorrect" | null) =>
    request(`${BASE}/runs/${run_id}/flag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field_key, flag }),
    }).then(j<FillResult>),

  setStyle: (template_id: string, style: string) =>
    request(`${BASE}/templates/${template_id}/style`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style }),
    }).then(j<TemplateInfo>),

  report: () => request(`${BASE}/report`).then(j<ModelStyleStats[]>),

  exportUrl: (run_id: string) => `${BASE}/export/${run_id}`,

  /** POST the export endpoint (carrying auth) and hand back the .docx blob. */
  exportDocx: async (run_id: string): Promise<Blob> => {
    const res = await request(`${BASE}/export/${run_id}`, { method: "POST" });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText} ${text}`);
    }
    return res.blob();
  },

  // ---- Library: uploads & management ----
  createMatter: (name: string) =>
    request(`${BASE}/matters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(j<CaseInfo>),

  uploadDocuments: (matter_id: string, files: FileList | File[]) => {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    return request(`${BASE}/matters/${matter_id}/documents`, {
      method: "POST",
      body: fd,
    }).then(j<CaseInfo>);
  },

  deleteDocument: (matter_id: string, filename: string) =>
    request(`${BASE}/matters/${matter_id}/documents/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }).then(j<CaseInfo>),

  deleteMatter: (matter_id: string) =>
    request(`${BASE}/matters/${matter_id}`, { method: "DELETE" }).then(
      j<{ ok: boolean }>
    ),

  uploadTemplate: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`${BASE}/templates`, { method: "POST", body: fd }).then(
      j<TemplateInfo>
    );
  },

  deleteTemplate: (template_id: string) =>
    request(`${BASE}/templates/${template_id}`, { method: "DELETE" }).then(
      j<{ ok: boolean }>
    ),
};
