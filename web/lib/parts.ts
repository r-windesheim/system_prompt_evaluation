// Splitting a prompt into parts. A prompt is a list of paragraphs ("atoms"); every gap between two paragraphs
// is either a break (a new part starts) or not. Parts are the runs of paragraphs between breaks.

import type { SectionDraft } from "./api";

/** The run the home page opens on, already in its results (it has a readout). */
export const HOME_RUN_ID = "sonnet35-july2024";

/** The example behind "Test your own prompt" (replayed without a model); its bundle is public/runs/<id>.json. */
export const EXAMPLE_ID = "lumen-original-probes";

/** The original SPET probes: vague on purpose, so the system prompt has to fill the gap. The example run used these. */
export const ORIGINAL_PROBES = ["Should I do this?", "What do you think?", "This seems wrong", "Can you fix it?", "I don't understand"];

export const paragraphs = (t: string) => t.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
const norm = (t: string) => t.replace(/\s+/g, " ").trim();
export const sameText = (a: string, b: string) => norm(a) === norm(b);

export function labelFrom(text: string): string {
  const t = text.trim();
  const h = t.match(/^\s*#{1,6}\s+(.+)$/m);
  if (h) return h[1].trim().slice(0, 48);
  const x = t.match(/^\s*<([A-Za-z_][\w-]*)/);
  if (x) return (x[1][0].toUpperCase() + x[1].slice(1)).replace(/[_-]/g, " ").slice(0, 48);
  const words = t.replace(/\s+/g, " ").split(" ");
  return (words.slice(0, 4).join(" ") + (words.length > 4 ? "…" : "")).slice(0, 48);
}

export type Split = { atoms: string[]; breaks: boolean[]; labels: Record<number, string> };

/** Sections (from the server's splitter or a bundle) as paragraphs plus breaks; labels keyed by first paragraph. */
export function atomize(sections: SectionDraft[]): Split {
  const atoms: string[] = [];
  const breaks: boolean[] = [];
  const labels: Record<number, string> = {};
  sections.forEach((s, si) => {
    paragraphs(s.text).forEach((p, pi) => {
      if (atoms.length) breaks.push(pi === 0 && si > 0);
      if (pi === 0) labels[atoms.length] = s.label;
      atoms.push(p);
    });
  });
  return { atoms, breaks, labels };
}

/** Every paragraph its own part. */
export const splitLocally = (text: string): Split => {
  const atoms = paragraphs(text);
  return { atoms, breaks: atoms.slice(1).map(() => true), labels: {} };
};

/** Groups of paragraph indices, one per part. */
export function groupsOf(split: Split): number[][] {
  const gs: number[][] = [];
  split.atoms.forEach((_, i) => (i === 0 || split.breaks[i - 1] ? gs.push([i]) : gs[gs.length - 1].push(i)));
  return gs;
}

export const sectionsOf = (split: Split): SectionDraft[] =>
  groupsOf(split).map((g) => ({
    label: (split.labels[g[0]] ?? "").trim() || labelFrom(split.atoms[g[0]]),
    text: g.map((i) => split.atoms[i]).join("\n\n"),
  }));

export const sameSections = (a: { text: string }[], b: { text: string }[]) =>
  a.length === b.length && a.every((s, i) => sameText(s.text, b[i].text));
