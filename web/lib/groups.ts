// Categorical colour per detector group. These are the only saturated colours
// besides the cobalt "ablation" signal. Values live in globals.css as --g-*.
export const GROUP_VAR: Record<string, string> = {
  Deference: "var(--g-deference)",
  Certainty: "var(--g-certainty)",
  Structure: "var(--g-structure)",
  Interaction: "var(--g-interaction)",
  Framing: "var(--g-framing)",
  Tone: "var(--g-tone)",
};

export const groupColor = (g: string) => GROUP_VAR[g] ?? "var(--graphite)";

export const fmtDelta = (d: number) => `${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d).toFixed(2)}`;
export const fmtQ = (q: number) => (q < 0.001 ? "q < 0.001" : `q = ${q.toFixed(3)}`);
