// Mirrors spet/bundle.py (schema_version 1-9). docs/run-bundle.schema.json is the source of truth.
// Fields added after v1 are optional here, because older bundles lack them.

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
  /** v4: the parts (section ids) each question was written for; null = not given. A question may target none. */
  query_targets?: number[][] | null;
  /**
   * v4: samples per question where it does not target the removed part (and in `full` where it targets no part).
   * null = n_per_query everywhere. When set, n_per_query is the count for targeted pairs only.
   */
  n_per_query_untargeted?: number | null;
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
  /** v4: question index of each per_query entry (questions without a pair are absent). */
  per_query_idx?: number[];
  mde?: number | null;
  flags?: Flag[];
};

export type Analysis = { n_tests: number; alpha: number; mde_alpha: number; warnings: string[] };

// ---- discovery (v3+; spet/discovery.py, docs/discovery.md) -----------------------------------------

export type PairExample = {
  query_idx: number;
  sample_idx: number;
  with_config?: string;
  without_config: string;
  with_yes: boolean;
};

/** y = yes, n = no, a = does not apply (NA), u = unreadable or failed. */
export type VerdictLetter = "y" | "n" | "a" | "u";

export type Statement = {
  id: string;
  section: number;
  text: string;
  /** v8: "authored" = written by a reviewer from the instruction text, blind to the answers (RunBundle.authored) */
  source: "intended" | "discovered" | "authored";
  classification?: "intended" | "side_effect" | null;
  full_rate: number;
  ablated_rate: number;
  full_rate_ci?: [number, number] | null;
  delta: number;
  ci: [number, number];
  ci_query?: [number, number] | null;
  p: number;
  q: number;
  significant: boolean;
  tested?: boolean;
  n_pairs: number;
  n_questions: number;
  verified_on?: number[];
  per_query?: number[];
  /** v4: question index of each per_query entry. */
  per_query_idx?: number[];
  mde?: number | null;
  n_unparseable?: number;
  n_na?: number;
  n_excluded_with?: number;
  n_excluded_without?: number;
  /** v4 */
  n_excluded_echo?: number;
  agreement?: number | null;
  kappa?: number | null;
  n_rejudged?: number;
  flags?: string[];
  examples?: PairExample[];
  /** v5: the Benjamini-Hochberg family of q; absent or null = before v5, one family for the whole run. */
  family?: "intended" | "discovered" | null;
  /** v5: [query_idx, sample_idx, with-part verdict + without-part verdict], e.g. [3, 0, "yn"]. */
  verdicts?: [number, number, string][];
  /** v5: [query_idx, sample_idx, side ("w" with the part, "o" without), verdict under the second prompt]. */
  rejudged?: [number, number, "w" | "o", string][];
  /** v8, authored: "reverse" = the statement says what the part asks the model NOT to do; rates stay the share judged yes. */
  polarity?: "positive" | "reverse";
  /** v8, authored: decided by an engine metric instead of the judge, e.g. "words <= 60"; null = judged. */
  measure?: string | null;
  /** v9: a short verb phrase that continues "The model ..." (the compliant behaviour); null = none, show the text. */
  label?: string | null;
};

export type PartReading = {
  section: number;
  adherence: "followed" | "partly_followed" | "redundant" | "not_followed" | "inconclusive" | "not_assessed";
  confirmed?: string[];
  side_effects?: string[];
  note?: string;
};

export type ScreenPick = { section: number; query_idx: number; sample_idx: number; lift?: number | null; call?: number };

/** v5: an attention screen ordered the proposer's pairs (it never enters a test). */
export type ScreenUse = {
  file: string;
  sha256: string;
  block: "reasoning" | "answer";
  model?: string | null;
  n_samples?: number | null;
  fingerprint: string;
  picked?: ScreenPick[];
};

export type Discovery = {
  /** tested statements in all families together */
  n_tests: number;
  n_statements: number;
  n_unreliable?: number;
  alpha: number;
  discovery_queries: number[];
  holdout_queries: number[];
  statements?: Statement[];
  readings?: PartReading[];
  calls?: Record<string, number>;
  n_unparseable?: number;
  n_errors?: number;
  /** v4: [config, query_idx, sample_idx] of answers that recite their own system prompt. */
  prompt_echoes?: [string, number, number][];
  /** unit of the sign-flip test; absent in v3 bundles, which used "cell". */
  test?: "cell" | "question";
  /** v5: tested statements per Benjamini-Hochberg family. */
  families?: Partial<Record<"intended" | "discovered", number>>;
  screen?: ScreenUse | null;
};

/** v6: how candidates were chosen from the screen, and when one counts as confirmed (fixed before any answer). */
export type ConfirmRule = {
  intended_p_below: number;
  discovered_p_below: number;
  require_tested?: boolean;
  excluded_flags?: string[];
  test?: "question";
  two_sided?: boolean;
  confirmed_if?: string;
};

export type ConfirmQuery = {
  text: string;
  /** the part it was written for; [] = a general question (side-effect checks) */
  targets?: number[];
  /** largest word overlap (Jaccard) with any question of the screen */
  overlap?: number;
};

/** v6: a screen statement retested on fresh questions. The Statement fields hold the confirmation's numbers, and
 * their question and sample indices refer to confirmation.queries and confirmation.responses. */
export type Candidate = Statement & {
  screen_p: number;
  screen_q: number;
  screen_full_rate: number;
  screen_ablated_rate: number;
  screen_delta: number;
  screen_n_questions: number;
  confirmed: boolean;
};

export type ConfirmReading = {
  section: number;
  adherence: PartReading["adherence"];
  /** "screen": no candidate of this part was confirmed, so the main run's reading stands */
  basis: "confirmation" | "screen";
  confirmed?: string[];
  not_confirmed?: string[];
  side_effects?: string[];
  note?: string;
};

/** v6: screen candidates, chosen by a fixed rule, retested on fresh questions with their own answers. */
export type Confirmation = {
  id: string;
  created_at: string;
  seed: number;
  alpha: number;
  rule: ConfirmRule;
  n_per_query: number;
  n_per_query_general: number;
  queries: ConfirmQuery[];
  configs: string[];
  /** query_idx indexes confirmation.queries */
  responses?: Response[];
  candidates?: Candidate[];
  families?: Partial<Record<"intended" | "discovered", number>>;
  n_tests?: number;
  readings?: ConfirmReading[];
  prompt_echoes?: [string, number, number][];
  calls?: Record<string, number>;
  n_unparseable?: number;
  n_errors?: number;
  n_cut_off?: number;
  warnings?: string[];
  settings?: Record<string, string | number | null>;
};

/** v7: one intended statement read two ways. `does`: does the model do it (an estimate from the with-part answers);
 * `cause`: is the part the reason ("confirmed" only from the confirmation run). */
export type Check = {
  id: string;
  text: string;
  /** which run the numbers come from; v8 "authored": the main run's answers, judged with an authored statement */
  data: "confirmation" | "screen" | "authored";
  /** share WITH the part that does what the part asks: for a reverse-coded statement, 1 - the share judged yes */
  rate_with: number;
  /** by-question bootstrap interval of rate_with */
  rate_with_ci?: [number, number] | null;
  rate_without: number;
  n_questions: number;
  /** judged answers per side */
  n_answers: number;
  does: "mostly" | "sometimes" | "rarely" | "unclear";
  cause: "confirmed" | "not_needed" | "not_shown";
  flags?: string[];
  note?: string;
  /** v8 */
  polarity?: "positive" | "reverse";
  /** v8: the share judged yes WITH the part, before any reversal */
  rate_with_raw?: number | null;
  /** v9: the statement's label; null = none */
  label?: string | null;
  /** v9: an author's note shown beside this check's example, from the run's annotations file */
  author_note?: string | null;
};

/** v7: an intended statement left out of the reading; reason starts "audit: " or "flag in the ... run: ". */
export type ExcludedCheck = { id: string; text: string; reason: string };

/** v7: one part's reading. Only "followed" carries a causal claim; "does_it" means the model does this but the part
 * was not shown to be the reason. */
export type PartReadout = {
  section: number;
  reading: "followed" | "not_needed" | "does_it" | "not_followed" | "partly_followed" | "unclear";
  /** the earlier reading (confirmation's if any, else discovery's), kept for compatibility */
  adherence: PartReading["adherence"];
  adherence_basis: "confirmation" | "screen";
  checks?: Check[];
  excluded?: ExcludedCheck[];
  side_effects?: string[];
  note?: string;
};

export type ReadoutRule = {
  mostly_at: number;
  rarely_at: number;
  excluded_flags?: string[];
  intended_only?: boolean;
};

export type AuditRecord = {
  file: string;
  sha256: string;
  reviewer: string;
  date: string;
  valid?: string[];
  invalid?: string[];
};

/** v7: two facts per intended statement and one reading per part (no model calls). */
/** v9: the annotations file the author notes came from. */
export type AnnotationsRecord = { file: string; sha256: string; author?: string; date?: string };

export type Readout = {
  created_at: string;
  rule: ReadoutRule;
  audit?: AuditRecord | null;
  parts?: PartReadout[];
  /** v9 */
  annotations?: AnnotationsRecord | null;
};

/** v8: author-written statements judged on the run's stored answers. Estimates only: not in any BH family, q = 1. */
export type Authored = {
  file: string;
  sha256: string;
  reviewer: string;
  date: string;
  created_at: string;
  statements?: Statement[];
  calls?: Record<string, number>;
  n_unparseable?: number;
  n_errors?: number;
  warnings?: string[];
  settings?: Record<string, string | number | null>;
  note?: string;
};

export type RunBundle = {
  schema_version: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
  meta: Meta;
  sections: Section[];
  configs: Config[];
  responses: Response[];
  detectors: Detector[];
  effects: Effect[];
  analysis?: Analysis | null;
  shapley?: Record<string, Record<string, number>> | null;
  discovery?: Discovery | null;
  /** v6 */
  confirmation?: Confirmation | null;
  /** v7 */
  readout?: Readout | null;
  /** v8 */
  authored?: Authored | null;
};

export type RunSummary = {
  meta: Meta;
  sections: Pick<Section, "id" | "label">[];
  nResponses: number;
  top: { detector: string; detectorLabel: string; section: number; sectionLabel: string; delta: number; q: number }[];
};
