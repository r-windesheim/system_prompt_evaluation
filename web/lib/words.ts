// Plain-language vocabulary for habits and metrics. One place, so every screen says the same thing.

export const NOUN: Record<string, string> = {
  apology: "apologies", sympathy: "sympathy lines", flattery: "compliments", hedge: "hedges", unclear: "“not sure what you mean” lines",
  booster: "certainty words", list_item: "bullet points", heading: "headings", bold: "bold phrases", parenthetical: "asides in brackets",
  question: "questions back", clarify: "requests for more context", offer: "offers of more help", caveat: "caveats",
  disclaimer: "disclaimers", meta: "meta comments", self_ai: "“as an AI” mentions", exclamation: "exclamation marks", emoji: "emoji",
  words: "words", lines: "lines", any_question: "answers with a question", ends_question: "answers ending in a question",
  any_list: "answers with a list", asks_context: "answers asking for context",
};

const MORE: Record<string, string> = {
  apology: "apologise more", sympathy: "sympathise more (“sorry to hear…”)", flattery: "compliment the user more", hedge: "hedge more",
  unclear: "say it doesn’t understand more often", booster: "sound more certain", list_item: "use more bullet points",
  heading: "use more headings", bold: "use more bold text", parenthetical: "add more asides in brackets", question: "ask more questions back",
  clarify: "ask for context more", offer: "offer more help at the end", caveat: "add more caveats", disclaimer: "add more disclaimers",
  meta: "talk more about its own answer", self_ai: "mention being an AI more", exclamation: "use more exclamation marks", emoji: "use more emoji",
};
const LESS: Record<string, string> = {
  apology: "apologise less", sympathy: "sympathise less", flattery: "compliment the user less", hedge: "hedge less",
  unclear: "say it doesn’t understand less often", booster: "sound less certain", list_item: "use fewer bullet points",
  heading: "use fewer headings", bold: "use less bold text", parenthetical: "add fewer asides in brackets", question: "ask fewer questions back",
  clarify: "ask for context less", offer: "offer more help less often", caveat: "add fewer caveats", disclaimer: "add fewer disclaimers",
  meta: "talk less about its own answer", self_ai: "mention being an AI less", exclamation: "use fewer exclamation marks", emoji: "use fewer emoji",
};

// Short names for the result buttons: "More bullet points", "Less hedging", "Shorter answers".
const SHORT: Record<string, [string, boolean]> = {
  apology: ["apologies", true], sympathy: ["sympathy", false], flattery: ["compliments", true], hedge: ["hedging", false],
  unclear: ["confusion", false], booster: ["certainty", false], list_item: ["bullet points", true], heading: ["headings", true],
  bold: ["bold text", false], parenthetical: ["asides", true], question: ["questions", true], clarify: ["requests for context", true],
  offer: ["offers of help", true], caveat: ["caveats", true], disclaimer: ["disclaimers", true], meta: ["meta comments", true],
  self_ai: ["AI mentions", true], exclamation: ["exclamation marks", true], emoji: ["emoji", false],
  lines: ["lines", true], any_list: ["lists", true], any_question: ["questions", true], ends_question: ["closing questions", true],
  asks_context: ["requests for context", true],
};
export function buttonLabel(d: string, delta: number, fallback?: string): string {
  if (d === "words") return delta > 0 ? "Longer answers" : "Shorter answers";
  const [name, countable] = SHORT[d] ?? [fallback ?? noun(d), true];
  return `${delta > 0 ? "More" : countable ? "Fewer" : "Less"} ${name}`;
}

export const noun = (d: string) => NOUN[d] ?? d;
export const phrase = (d: string, delta: number) => (delta > 0 ? MORE : LESS)[d] ?? `${delta > 0 ? "more" : "fewer"} ${noun(d)}`;
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const FLAG_TEXT: Record<string, string> = {
  in_lists: "Mostly inside bullet lists, so this may come from the formatting rather than from the habit itself.",
  length_shift: "This instruction also changes how long answers are, which moves most counts. Part of this effect may come from length.",
  context_shift: "This instruction sets who the assistant is, so removing it changes what the answers are about, not just their style.",
  not_testable: "These questions never gave this habit a chance to change.",
};

/** Plain-language q-value: the expected share of false findings among those reported at this cutoff. */
export const qText = (q: number) => (q < 0.001 ? "under 0.1%" : `${(q * 100).toFixed(q < 0.01 ? 1 : 0)}%`);

/** One of a habit, for sentences like "about one bullet point per two answers". */
const SINGULAR: Record<string, string> = {
  apology: "apology", sympathy: "sympathy line", flattery: "compliment", hedge: "hedge", unclear: "“not sure what you mean” line",
  booster: "certainty word", list_item: "bullet point", heading: "heading", bold: "bold phrase", parenthetical: "aside in brackets",
  question: "question back", clarify: "request for more context", offer: "offer of more help", caveat: "caveat", disclaimer: "disclaimer",
  meta: "meta comment", self_ai: "“as an AI” mention", exclamation: "exclamation mark", emoji: "emoji", words: "word", lines: "line",
};
export const singular = (d: string, fallback?: string) => SINGULAR[d] ?? fallback ?? noun(d);

/** Short flag names for chips that sit next to a number. */
export const FLAG_SHORT: Record<string, string> = { in_lists: "inside lists", length_shift: "partly length", context_shift: "changes topic" };

/** What a share-of-answers metric means, as a predicate: "of answers have a list". */
export const SHARE_PRED: Record<string, string> = {
  any_list: "have a list", any_question: "ask a question", ends_question: "end on a question", asks_context: "ask for more context",
};

const METRIC_MORE: Record<string, string> = { words: "write longer answers", lines: "use more lines", any_list: "use a list more often", any_question: "ask a question more often", ends_question: "end on a question more often", asks_context: "ask for context more often" };
const METRIC_LESS: Record<string, string> = { words: "write shorter answers", lines: "use fewer lines", any_list: "use a list less often", any_question: "ask a question less often", ends_question: "end on a question less often", asks_context: "ask for context less often" };
/** Like phrase(), but also covers the answer-shape metrics. */
export const phraseAny = (d: string, delta: number, label?: string) =>
  (delta > 0 ? METRIC_MORE : METRIC_LESS)[d] ?? (d in MORE ? phrase(d, delta) : `${delta > 0 ? "more" : "fewer"} ${label ?? noun(d)}`);

/** Rounded count per answer, in words: "about 2 bullet points per answer", "about one sympathy line per three answers", "almost none". */
const SMALL = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
export function approxCount(x: number, d: string, label?: string): string {
  if (x <= 0) return `no ${noun(d)}`;
  if (x < 0.08) return `almost no ${noun(d)}`;
  if (x < 0.6) {
    const n = Math.round(1 / x);
    return `about one ${singular(d, label)} per ${SMALL[n] ?? n} answers`;
  }
  const n = Math.round(x);
  return `about ${n === 1 ? "one" : n} ${n === 1 ? singular(d, label) : noun(d)} per answer`;
}
/** Rounded word count: "about 60 words". */
export const approxWords = (x: number) => `about ${x < 30 ? Math.round(x) : Math.round(x / 5) * 5} words`;
/** Rounded share of answers in words: "about half", "almost all". */
export function approxShare(p: number): string {
  if (p <= 0) return "none";
  if (p < 0.06) return "almost none";
  if (p > 0.97) return "all";
  if (p > 0.9) return "almost all";
  const named: [number, string][] = [[0.1, "about one in ten"], [0.2, "about one in five"], [0.25, "about a quarter"], [0.33, "about a third"], [0.5, "about half"], [0.67, "about two thirds"], [0.75, "about three quarters"], [0.85, "most"]];
  return named.reduce((a, z) => (Math.abs(z[0] - p) < Math.abs(a[0] - p) ? z : a))[1];
}
