// Everything the page derives from a run bundle, in one place. Components read only this.
// Works on schema v1 bundles: kind, tested, flags, per_query, ci_query, mde, notes and analysis may all be missing.

import type { Detector, Effect, Response, RunBundle, Section } from "@/lib/types";
import { approxCount, approxShare, approxWords, buttonLabel, cap, FLAG_SHORT, FLAG_TEXT, noun, phraseAny, qText, SHARE_PRED } from "@/lib/words";

/** v1 bundles have no detector.kind; these ids were always shape metrics. */
const METRIC_IDS = new Set(["words", "lines", "any_question", "ends_question", "any_list", "asks_context"]);
const SHARE_IDS = new Set(["any_question", "ends_question", "any_list", "asks_context"]);
/** Shape metrics whose answers can still be highlighted, via the habit they are built from. */
const HIGHLIGHT_VIA: Record<string, string> = { any_list: "list_item", any_question: "question", ends_question: "question" };
const SMALL = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const listJoin = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
export const wordCount = (t: string) => t.split(/\s+/).filter(Boolean).length;

export type Example = { q: number; s: number };
export type Run = ReturnType<typeof indexRun>;
export type NoteKind = "found" | "none" | "untestable";
export type Note = {
  kind: NoteKind;
  /** the button's name: "More bullet points", "No change" */
  says: string;
  /** "and three other habits" */
  also: string;
  /** the change the figure shows */
  main: Effect | null;
};
export type DetailRow = { label: string; withIt: string; without: string; flags: string[] };

export function indexRun(b: RunBundle) {
  const det = new Map<string, Detector>(b.detectors.map((d) => [d.id, d]));
  const sections = b.sections;
  const secById = new Map<number, Section>(sections.map((s) => [s.id, s]));
  const nQ = b.meta.queries.length;
  const nS = b.meta.n_per_query;

  const isMetric = (d: string) => {
    const k = det.get(d)?.kind;
    return k ? k === "metric" : METRIC_IDS.has(d);
  };
  const isShare = (d: string) => det.get(d)?.unit === "share of answers" || SHARE_IDS.has(d);
  const label = (d: string) => det.get(d)?.label?.toLowerCase();
  const nounOf = (d: string) => (noun(d) === d ? label(d) ?? d : noun(d));

  // configs map a removed section id to a config id; never assume "without_k" or array order
  const cfg = new Map<number | null, string>(b.configs.map((c) => [c.removed, c.id]));
  const resp = new Map<string, Response>(b.responses.map((r) => [`${r.config}|${r.query_idx}|${r.sample_idx}`, r]));
  const response = (removed: number | null, q: number, s: number): Response | undefined => {
    const c = cfg.get(removed);
    return c === undefined ? undefined : resp.get(`${c}|${q}|${s}`);
  };

  const eff = new Map<string, Effect>(b.effects.map((e) => [`${e.section}|${e.detector}`, e]));
  const effect = (k: number, d: string) => eff.get(`${k}|${d}`);

  /** The section's own "never tested: …" note, as a plain sentence; null if the part was testable. */
  const untestableReason = (k: number): string | null => {
    const n = (secById.get(k)?.notes ?? []).find((x) => /^never tested/i.test(x));
    if (n === undefined) return null;
    const body = n.replace(/^never tested:?\s*/i, "").trim().replace(/\.$/, "");
    return body ? `${cap(body)}.` : "These questions never gave it a chance to change anything.";
  };
  const untestable = (k: number) => untestableReason(k) !== null;
  const isTested = (e: Effect) => e.tested !== false && !(e.flags ?? []).includes("not_testable");

  /** Significant findings for a part: habits first (largest change first), then shape metrics. */
  const findings = (k: number): Effect[] =>
    untestable(k)
      ? []
      : b.effects
          .filter((e) => e.section === k && det.has(e.detector) && e.significant && isTested(e))
          .sort((a, z) => Number(isMetric(a.detector)) - Number(isMetric(z.detector)) || relSize(z) - relSize(a));
  const habitFindings = (k: number) => findings(k).filter((e) => !isMetric(e.detector)).sort((a, z) => Math.abs(z.delta) - Math.abs(a.delta));
  const shapeFindings = (k: number) => findings(k).filter((e) => isMetric(e.detector));
  const testedCount = (k: number) => b.effects.filter((e) => e.section === k && det.has(e.detector) && isTested(e)).length;
  const neverSeen = (k: number) =>
    b.effects.filter((e) => e.section === k && det.has(e.detector) && !isTested(e) && !isMetric(e.detector)).map((e) => nounOf(e.detector));

  /** The change that best shows what a part does: the largest habit change; else the largest shape change. */
  const mainFinding = (k: number): Effect | null => habitFindings(k)[0] ?? shapeFindings(k)[0] ?? null;
  const highlightFor = (d: string | null | undefined) => (!d ? null : isMetric(d) ? HIGHLIGHT_VIA[d] ?? null : d);

  function note(k: number): Note {
    if (untestable(k)) return { kind: "untestable", says: "Not testable", also: "", main: null };
    const main = mainFinding(k);
    if (!main) return { kind: "none", says: "No change", also: "", main: null };
    const others = isMetric(main.detector) ? shapeFindings(k).length - 1 : habitFindings(k).length - 1;
    const what = isMetric(main.detector) ? "change" : "habit";
    const also = others > 0 ? `and ${SMALL[others] ?? others} other ${what}${others === 1 ? "" : "s"}` : "";
    return { kind: "found", says: buttonLabel(main.detector, main.delta, nounOf(main.detector)), also, main };
  }

  /** Rounded figure for the margin: "1.8", "61 words", "55%". */
  const figure = (d: string, x: number) =>
    x === 0 ? "none" : isShare(d) ? `${Math.round(x * 100)}%` : d === "words" ? `${Math.round(x)} words` : x >= 10 ? x.toFixed(0) : x.toFixed(1);
  /** What the figure counts, where the number alone would not say it. */
  const figureUnit = (d: string) => (isShare(d) ? "of answers" : d === "words" ? "" : "per answer");

  const fmtMean = (d: string, x: number) => (isShare(d) ? `${Math.round(x * 100)}%` : d === "words" ? x.toFixed(0) : x.toFixed(2));

  /** One plain sentence for a finding: "the model writes about 2 bullet points per answer. Without it, almost none." */
  function findingSentence(e: Effect): string {
    const d = e.detector;
    if (d === "words") return `answers run ${approxWords(e.full_mean)}. Without it, ${approxWords(e.ablated_mean)}.`;
    if (isShare(d)) {
      const pred = SHARE_PRED[d] ?? `count as ${nounOf(d)}`;
      return `${approxShare(e.full_mean)} of answers ${pred}. Without it, ${approxShare(e.ablated_mean)} do.`;
    }
    if (isMetric(d)) return `the model tends to ${phraseAny(d, e.delta, nounOf(d))}: ${fmtMean(d, e.full_mean)} against ${fmtMean(d, e.ablated_mean)} without it.`;
    const a = e.ablated_mean;
    const without = a <= 0 ? "none at all" : a < 0.08 ? "almost none" : approxCount(a, d, label(d));
    return `the model writes ${approxCount(e.full_mean, d, label(d))}. Without it, ${without}.`;
  }

  /** The one sentence an opened part starts with. */
  function sentence(k: number): string {
    const why = untestableReason(k);
    if (why !== null) return why;
    const main = mainFinding(k);
    if (!main) return "SPET found no measurable difference between answers with and without this part.";
    let s = `With this part, ${findingSentence(main)}`;
    const rest = isMetric(main.detector) ? [] : habitFindings(k).slice(1);
    const more = rest.filter((e) => e.delta > 0).map((e) => nounOf(e.detector));
    const less = rest.filter((e) => e.delta < 0).map((e) => nounOf(e.detector));
    if (more.length) s += ` It also brings more ${listJoin(more)}.`;
    if (less.length) s += ` It${more.length ? "" : " also"} brings fewer ${listJoin(less)}.`;
    return s;
  }

  function measure(r: Response | undefined, d: string): number {
    if (!r) return 0;
    if (d === "words") return wordCount(r.text);
    if (d === "lines") return r.text.split("\n").filter((l) => l.trim()).length;
    const via = HIGHLIGHT_VIA[d];
    if (via) return r.spans.some((s) => s.detector === via) ? 1 : 0;
    return r.spans.filter((s) => s.detector === d).length;
  }

  /**
   * A pair of answers that shows the part's main change at a typical size, preferring short answers so the pair
   * reads at a glance. With no finding: a short pair, as a plain sample of what both versions say.
   */
  function example(k: number): Example | null {
    if (untestable(k)) return null;
    const e = mainFinding(k);
    const sign = e && e.delta < 0 ? -1 : 1;
    const target = !e ? 0 : e.detector === "words" ? Math.abs(e.delta) * 0.6 : isShare(e.detector) ? 1 : Math.max(1, Math.round(Math.abs(e.delta)));
    let best: Example | null = null;
    let bestLen = Infinity;
    let fallback: Example | null = null;
    let fv = -Infinity;
    for (let q = 0; q < nQ; q++)
      for (let s = 0; s < nS; s++) {
        const a = response(null, q, s);
        const z = response(k, q, s);
        if (!a || !z) continue;
        const wa = wordCount(a.text);
        const wz = wordCount(z.text);
        if (Math.min(wa, wz) < 6) continue;
        const len = wa + wz + (e ? 0 : Math.abs(wa - wz));
        if (!e) {
          if (len < bestLen) { bestLen = len; best = { q, s }; }
          continue;
        }
        const v = sign * (measure(a, e.detector) - measure(z, e.detector));
        if (v > fv) { fv = v; fallback = { q, s }; }
        if (v >= target && len < bestLen) { bestLen = len; best = { q, s }; }
      }
    return best ?? fallback;
  }

  const rowLabel = (d: string) =>
    d === "words" ? "Words per answer" : d === "lines" ? "Lines per answer" : isShare(d) ? cap(nounOf(d)) : `${cap(nounOf(d))} per answer`;
  const flagsOf = (e: Effect) => (e.flags ?? []).filter((f) => f !== "not_testable");

  /** Everything "More detail" shows for a part: the exact numbers, their caveats and the run's warnings. */
  function detail(k: number) {
    const fs = findings(k);
    const rows: DetailRow[] = fs.map((e) => ({
      label: rowLabel(e.detector),
      withIt: fmtMean(e.detector, e.full_mean),
      without: fmtMean(e.detector, e.ablated_mean),
      flags: flagsOf(e).map((f) => FLAG_SHORT[f] ?? f),
    }));
    const flagNotes = [...new Set(fs.flatMap(flagsOf))]
      .filter((f) => FLAG_TEXT[f])
      .map((f) => ({ short: FLAG_SHORT[f] ?? f, text: FLAG_TEXT[f].replace(/^This instruction/, "This part") }));
    // with an untargeted count (v4), a question is asked nS times where it targets part k and nU times elsewhere
    const nU = b.meta.n_per_query_untargeted ?? null;
    const nT = nU === null ? nQ : (b.meta.query_targets ?? []).filter((t) => t.includes(k)).length;
    const times = (n: number) => `${n} time${n === 1 ? "" : "s"}`;
    const asked =
      nU === null || nU === nS || nT === nQ
        ? `asked ${times(nU === null || nT === nQ ? nS : nU)} each`
        : nT === 0
          ? `asked ${times(nU)} each`
          : `asked ${times(nS)} each if written for this part (${nT} of them) and ${times(nU)} otherwise`;
    const nPairs = fs[0]?.n_pairs ?? nT * nS + (nQ - nT) * (nU ?? nS);
    const paras: string[] = [];
    if (fs.length) {
      const qmax = Math.max(...fs.map((e) => e.q));
      paras.push(
        `Each figure is an average over ${nPairs} answers: ${nQ} question${nQ === 1 ? "" : "s"}, ${asked}, to ${b.meta.model}. ` +
          `Only differences unlikely to be chance are listed; at most ${qText(qmax)} of findings at this level are expected to be false.`,
      );
    } else if (!untestable(k)) {
      const n = testedCount(k);
      const mde = b.effects.some((e) => e.section === k && typeof e.mde === "number");
      paras.push(
        `SPET compared ${n} habit${n === 1 ? "" : "s"}, from apologies to answer length, across ${nPairs} answers with and ${nPairs} without this part. ` +
          `None moved by more than chance would explain.${mde ? " A smaller change could still be hiding below what this many answers can show." : ""}`,
      );
    }
    const unseen = neverSeen(k);
    if (unseen.length && !untestable(k) && !fs.length)
      paras.push(`${cap(SMALL[unseen.length] ?? String(unseen.length))} habits never showed up with or without this part, so they could not be checked: ${listJoin(unseen)}.`);
    return { rows, flagNotes, paras, warnings: b.analysis?.warnings ?? [] };
  }

  /** A short form of the untestable reason for the margin, or null if it doesn't shorten well. */
  const untestableShort = (k: number): string | null => {
    const why = untestableReason(k);
    if (!why) return null;
    const head = why.split(/, so |; /)[0].replace(/\.$/, "");
    return head.length <= 90 ? head : null;
  };

  return {
    b, meta: b.meta, sections, nQ, nS, testedCount, untestableShort,
    response, effect, untestable, findings, note, figure, figureUnit, sentence, example, highlightFor, detail, isMetric,
  };
}

/** Relative size of a change, for ordering mixed units. */
export const relSize = (e: Effect) => Math.abs(e.delta) / Math.max(Math.abs(e.full_mean), Math.abs(e.ablated_mean), 1e-9);
