// Mirrors spet/bundle.py (schema_version 1). docs/run-bundle.schema.json is the source of truth.

export type Meta = {
  id: string;
  title: string;
  created_at: string;
  model: string;
  provider: string;
  temperature: number;
  n_per_query: number;
  seed: number;
  queries: string[];
  fixture: boolean;
  notes: string;
  settings?: Record<string, string | number | null>;
};

export type Section = { id: number; label: string; text: string; notes?: string[] };
export type Config = { id: string; removed: number | null };
export type Span = { start: number; end: number; detector: string };

export type Response = {
  config: string;
  query_idx: number;
  sample_idx: number;
  text: string;
  spans: Span[];
  finish_reason?: string | null;
};

export type Detector = {
  id: string;
  label: string;
  group: string;
  description: string;
  kind?: "habit" | "metric";
  unit: string;
  precision: number | null;
  precision_n: number | null;
  precision_model?: string | null;
};

export type Flag = "in_lists" | "length_shift" | "context_shift" | "not_testable";

export type Effect = {
  detector: string;
  section: number;
  full_mean: number;
  ablated_mean: number;
  delta: number;
  ci: [number, number];
  p: number;
  q: number;
  significant: boolean;
  n_pairs: number;
  tested?: boolean;
  ci_query?: [number, number] | null;
  per_query?: number[];
  mde?: number | null;
  flags?: Flag[];
};

export type Analysis = { n_tests: number; alpha: number; mde_alpha: number; warnings: string[] };

export type RunBundle = {
  schema_version: 1 | 2;
  meta: Meta;
  sections: Section[];
  configs: Config[];
  responses: Response[];
  detectors: Detector[];
  effects: Effect[];
  analysis?: Analysis | null;
  shapley?: Record<string, Record<string, number>> | null;
};

export type RunSummary = {
  meta: Meta;
  sections: Pick<Section, "id" | "label">[];
  nResponses: number;
  top: { detector: string; detectorLabel: string; section: number; sectionLabel: string; delta: number; q: number }[];
};
