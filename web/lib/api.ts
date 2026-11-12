// Client for `spet serve`. When NEXT_PUBLIC_SPET_API is unset (the hosted static
// site), the analyse flow is unavailable and only recorded runs are shown.
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
export type RunListItem = {
  id: string;
  title: string;
  model: string;
  created_at: string;
  fixture: boolean;
  n_sections: number;
  n_responses: number;
  n_significant: number;
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
  list: () => call<{ runs: RunListItem[]; running: RunStatus[] }>("/api/runs"),
};

/** Where a run's bundle lives: the API when it's running locally, else the static export. */
export const bundleUrl = (id: string) =>
  hasApi ? `${API}/api/runs/${encodeURIComponent(id)}` : `${BASE}/runs/${encodeURIComponent(id)}.json`;
