// The small view a run with a readout is shown from. Built at build time from the bundle (lib/view.server.ts);
// the browser never downloads the bundle. The overview comes with the page; one part's answers are fetched when
// that part is opened (or about to be).

export type Reading = "followed" | "does_it" | "not_needed" | "partly_followed" | "not_followed" | "unclear";

/** The one button per part: the reading, nothing else. Only "followed" carries the accent. */
export const BUTTON: Record<Reading, string> = {
  followed: "Followed",
  does_it: "Does it",
  not_needed: "Does it anyway",
  partly_followed: "Partly followed",
  not_followed: "Not followed",
  unclear: "Unclear",
};

export type CheckDetail = {
  id: string;
  /** the statement the judge read, verbatim */
  statement: string;
  /** "Says it cannot open the link and asks for the text: mostly (almost all of the answers with this part, ...)." */
  line: string;
  withPct: string;
  withoutPct: string;
  /** small print under the statement in "More detail" */
  notes: string[];
  /** false: same numbers as an earlier check of the part, so its line is folded into that one under the sentence */
  shown: boolean;
};

export type PartOverview = {
  k: number;
  label: string;
  text: string;
  reading: Reading;
  /** a confirmed side effect exists: a dot beside the button and an item in the opened part */
  side: boolean;
};

export type RunView = {
  id: string;
  title: string;
  model: string;
  /** one plain line under the headline */
  lede: string;
  /** the quiet footer line, before the Method link */
  size: string;
  parts: PartOverview[];
};

export type Answer = { text: string; words: number; cut: boolean };

export type Pair = {
  question: string;
  /** "main": the main run's answers; "confirmation": the second test's, on new questions */
  from: "main" | "confirmation";
  with: Answer;
  without: Answer;
  /** a plain note beside one answer, e.g. that it describes a page the model never read */
  note: { side: "with" | "without"; text: string } | null;
};

export type DrewRow = { k: number; label: string; first: string; lift: number; tint: 1 | 2 | 3 };

export type PartFile = {
  k: number;
  /** answers "does the model do what this says?" */
  sentence: string;
  /** one line per check under the sentence, and its numbers under "More detail" */
  checks: CheckDetail[];
  /** paragraphs under the table in "More detail" */
  deep: string[];
  example: Pair | null;
  /** null: the example's question is not in the attention screen, so "What it drew on" is hidden */
  drew: { question: string; rows: DrewRow[]; stoodOut: boolean } | null;
  side: { sentence: string; pair: Pair | null } | null;
};

// ---- words --------------------------------------------------------------------------------------------

const NAMED: [number, string][] = [
  [0.07, "a few"], [0.1, "about one in ten"], [0.15, "about one in seven"], [0.2, "about one in five"],
  [0.25, "about a quarter"], [0.33, "about a third"], [0.4, "about two in five"], [0.5, "about half"],
  [0.6, "about three in five"], [0.67, "about two thirds"], [0.75, "about three quarters"], [0.85, "most"],
];
/** A share in words. "all" and "none" only when exact, so a rounded word never claims more than the data. */
export function share(p: number): string {
  if (p >= 1) return "all";
  if (p <= 0) return "none";
  if (p < 0.06) return "almost none";
  if (p >= 0.9) return "almost all";
  return NAMED.reduce((a, z) => (Math.abs(z[0] - p) < Math.abs(a[0] - p) ? z : a))[1];
}
export const pct = (p: number) => `${Math.round(p * 100)}%`;
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const firstLine = (t: string) => t.split("\n")[0].trim();
