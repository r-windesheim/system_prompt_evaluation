// Client for `spet serve`. When NEXT_PUBLIC_SPET_API is unset (the hosted static
// site), only the example and recorded runs can be shown.
export const API = (process.env.NEXT_PUBLIC_SPET_API ?? "").replace(/\/$/, "");
export const hasApi = API.length > 0;
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export type SectionDraft = { label: string; text: string };
export type Health = { ok: boolean; base_url: string | null; model: string | null; default_queries: string[] };
export type RunStatus = {
  id: string;
  state: "running" | "done" | "error";
  done?: number;
  total?: number;
  error?: string | null;
  configs?: string[];
  per_config?: Record<string, number>;
  per_config_total?: number;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {}
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => call<Health>("/api/health"),
  split: (prompt: string, endpoint?: { base_url?: string; model?: string }) =>
    call<{ method: "model" | "heuristic"; sections: SectionDraft[] }>("/api/split", {
      method: "POST",
      body: JSON.stringify({ prompt, use_model: true, endpoint }),
    }),
  start: (body: {
    title: string;
    sections: SectionDraft[];
    queries: string[];
    n_per_query: number;
    temperature: number;
    endpoint?: { base_url?: string; model?: string };
  }) => call<{ id: string; total: number }>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  status: (id: string) => call<RunStatus>(`/api/runs/${encodeURIComponent(id)}/status`),
};

export const staticBundleUrl = (id: string) => `${BASE}/runs/${encodeURIComponent(id)}.json`;
/** Path of a run's own page, for links and for the address bar once a live run finishes. */
export const runPath = (id: string) => `${BASE}/run/?id=${encodeURIComponent(id)}`;

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

export const apiBundleUrl = (id: string) => `${API}/api/runs/${encodeURIComponent(id)}`;

/** A run's bundle: from the local API when there is one (it also holds runs made here), else the static export. */
export async function loadBundle<T>(id: string): Promise<T> {
  if (!hasApi) return getJson<T>(staticBundleUrl(id));
  try {
    return await getJson<T>(apiBundleUrl(id));
  } catch {
    return getJson<T>(staticBundleUrl(id));
  }
}
export const loadStatic = <T,>(id: string) => getJson<T>(staticBundleUrl(id));
