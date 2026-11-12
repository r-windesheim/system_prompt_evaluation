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
};

export type Section = { id: number; label: string; text: string };
export type Config = { id: string; removed: number | null };
export type Span = { start: number; end: number; detector: string };

export type Response = {
  config: string;
  query_idx: number;
  sample_idx: number;
  text: string;
  spans: Span[];
};

export type Detector = {
  id: string;
  label: string;
  group: string;
  description: string;
  unit: "per response";
  precision: number | null;
  precision_n: number | null;
};

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
};

export type RunBundle = {
  schema_version: 1;
  meta: Meta;
  sections: Section[];
  configs: Config[];
  responses: Response[];
  detectors: Detector[];
  effects: Effect[];
  shapley?: Record<string, Record<string, number>> | null;
};

export type RunSummary = {
  meta: Meta;
  sections: Pick<Section, "id" | "label">[];
  nResponses: number;
  top: { detector: string; detectorLabel: string; section: number; sectionLabel: string; delta: number; q: number }[];
};
