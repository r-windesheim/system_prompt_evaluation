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

export const noun = (d: string) => NOUN[d] ?? d;
export const phrase = (d: string, delta: number) => (delta > 0 ? MORE : LESS)[d] ?? `${delta > 0 ? "more" : "fewer"} ${noun(d)}`;
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const f1 = (x: number) => (Math.abs(x) < 0.05 ? "0" : x.toFixed(1));
export const f2 = (x: number) => x.toFixed(2);
export const signed = (x: number, digits = 1) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(digits)}`;

export const FLAG_TEXT: Record<string, string> = {
  in_lists: "Mostly inside bullet lists, so this may come from the formatting rather than from the habit itself.",
  length_shift: "This part also changes how long answers are, which moves most counts. Part of this effect may come from length.",
  context_shift: "This part sets who the assistant is, so removing it changes what the answers are about, not just their style.",
  not_testable: "These questions never gave this habit a chance to change.",
};

/** Plain-language q-value: the expected share of false findings among those reported at this cutoff. */
export const qText = (q: number) => (q < 0.001 ? "under 0.1%" : `${(q * 100).toFixed(q < 0.01 ? 1 : 0)}%`);
