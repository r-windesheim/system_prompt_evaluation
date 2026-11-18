import "server-only";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Check, PartReadout, Response, RunBundle, Statement } from "./types";
import {
  cap, firstLine, pct, share, type Answer, type CheckDetail, type DrewRow, type Pair, type PartFile, type PartOverview,
  type Reading, type RunView,
} from "./view";
import { loadRun, runIds } from "./runs.server";

// ---- loading (each bundle parsed once per build) ------------------------------------------------------------

const bundles = new Map<string, RunBundle>();
function bundle(id: string): RunBundle {
  let b = bundles.get(id);
  if (!b) bundles.set(id, (b = loadRun(id)));
  return b;
}

type Screen = { sha256: string; lift: Record<string, (number | null)[]> };
function screen(id: string): Screen | null {
  const f = path.join(process.cwd(), "data", "screens", `${id}.json`);
  if (!existsSync(f)) return null;
  const s = JSON.parse(readFileSync(f, "utf8")) as Screen;
  // a screen made for other questions is never shown
  const want = bundle(id).discovery?.screen?.sha256;
  return want && want !== s.sha256 ? null : s;
}

/** Runs shown through the readout view: those whose bundle has a readout. */
export function readoutIds(): string[] {
  return runIds().filter((id) => (bundle(id).readout?.parts?.length ?? 0) > 0);
}
export const hasReadout = (id: string) => readoutIds().includes(id);

// ---- what one check rests on ----------------------------------------------------------------------------------

function statementOf(b: RunBundle, c: Check): Statement | undefined {
  const pool: Statement[] =
    c.data === "confirmation" ? b.confirmation?.candidates ?? [] : c.data === "authored" ? b.authored?.statements ?? [] : b.discovery?.statements ?? [];
  return pool.find((s) => s.id === c.id);
}

/** The verdict letter means "does what the part asks": a reverse-coded statement says the opposite. */
const doesWhat = (letter: string, reverse: boolean) => (letter === "y") !== reverse;


/** The check that gives the part its example: a confirmed one if any, else the first. */
const leadOf = (p: PartReadout): Check | undefined => p.checks?.find((c) => c.cause === "confirmed") ?? p.checks?.[0];

/** The more common of "y" and "n" among one side's stored verdicts; null on a tie or with none. */
function majority(vs: [number, number, string][], side: 0 | 1): "y" | "n" | null {
  let y = 0;
  let n = 0;
  for (const [, , v] of vs) {
    if (v[side] === "y") y++;
    else if (v[side] === "n") n++;
  }
  return y > n ? "y" : n > y ? "n" : null;
}

/**
 * The example pair, by a fixed rule, in the order the verdicts are stored (question order, then sample).
 * A confirmed check: the first pair that differs in the direction of the finding (with the part it does what the
 * part asks, without it it does not). Any other check: a typical pair, not an exceptional one: the first pair whose
 * two verdicts are the majority verdict with the part and the majority verdict without it; failing that, the first
 * pair whose with-part verdict is the majority one. Last fallback: the first pair with two readable verdicts.
 */
function pickPair(b: RunBundle, c: Check) {
  const s = statementOf(b, c);
  const reverse = c.polarity === "reverse";
  const all = s?.verdicts ?? [];
  const readable = all.filter(([, , v]) => /^[yn][yn]$/.test(v));
  let pick: [number, number, string] | undefined;
  if (c.cause === "confirmed") {
    const dir = Math.sign(c.rate_with - c.rate_without);
    if (dir !== 0) pick = readable.find(([, , v]) => doesWhat(v[0], reverse) === dir > 0 && doesWhat(v[1], reverse) === dir < 0);
  } else {
    const w = majority(all, 0);
    const o = majority(all, 1);
    pick =
      readable.find(([, , v]) => (w === null || v[0] === w) && (o === null || v[1] === o)) ??
      readable.find(([, , v]) => w === null || v[0] === w);
  }
  pick ??= readable[0];
  return pick ? { q: pick[0], s: pick[1], v: pick[2], reverse } : null;
}

const words = (t: string) => t.split(/\s+/).filter(Boolean).length;
const answer = (r: Response): Answer => ({ text: r.text, words: words(r.text), cut: r.finish_reason === "length" });

function responses(b: RunBundle, from: "main" | "confirmation") {
  const list = from === "main" ? b.responses : b.confirmation?.responses ?? [];
  const cfg = new Map<number | null, string>(from === "main" ? b.configs.map((c) => [c.removed, c.id]) : []);
  const m = new Map(list.map((r) => [`${r.config}|${r.query_idx}|${r.sample_idx}`, r]));
  const name = (removed: number | null) => (from === "main" ? cfg.get(removed) : removed === null ? "full" : `without_${removed}`);
  return (removed: number | null, q: number, s: number) => m.get(`${name(removed)}|${q}|${s}`);
}

function pairFor(b: RunBundle, k: number, c: Check): { pair: Pair; q: number } | null {
  const pick = pickPair(b, c);
  if (!pick) return null;
  const from = c.data === "confirmation" ? "confirmation" : "main";
  const get = responses(b, from);
  const a = get(null, pick.q, pick.s);
  const z = get(k, pick.q, pick.s);
  if (!a || !z) return null;
  const question = from === "main" ? b.meta.queries[pick.q] : b.confirmation!.queries[pick.q].text;
  // an author's note on the check (the run's annotations file), shown beside the example as a note
  const note = c.author_note ? c.author_note : null;
  return { pair: { question, from, with: answer(a), without: answer(z), note }, q: pick.q };
}

// ---- words for a part: templates from the reading and the numbers, nothing per run ------------------------------

/** What a check is called: the bundle's label, else the statement itself. */
const labelOf = (c: Check) => cap(c.label?.trim() || c.text.replace(/\.$/, ""));

/** "almost all answers", "about a third of answers", "no answers". */
function answers(p: number): string {
  const w = share(p);
  if (w === "none") return "no answers";
  if (w === "almost none") return "almost no answers";
  if (/^(all|almost all|most|a few|about (one|two|three) in)/.test(w)) return `${w} answers`;
  return `${w} of answers`;
}

/** "Says it cannot open the link: almost all answers with it, about two thirds without." */
function line(c: Check): string {
  const w = share(c.rate_with);
  const o = share(c.rate_without);
  return w === o ? `${labelOf(c)}: ${w}, with or without it.` : `${labelOf(c)}: ${answers(c.rate_with)} with it, ${o} without.`;
}

/** Answers "does the model do what this part says?". Only "followed" (a confirmed check) names the part as the cause. */
const SENTENCE: Record<Reading, string> = {
  followed: "Yes, because of this part.",
  does_it: "Mostly, but not clearly because of this part.",
  not_needed: "Yes, with or without this part.",
  partly_followed: "Partly.",
  not_followed: "No.",
  unclear: "Could not be checked.",
};

const fmtP = (p: number) => (p < 0.001 ? "below 0.001" : p < 0.01 ? p.toFixed(3) : p.toFixed(2));

/**
 * A row of "More detail": the statement as the judge read it, and the share of answers where it holds, with and
 * without the part. For a reverse-coded statement (the part asks for the opposite) that is the raw share judged yes,
 * so the row reads true to its statement, and the row says it is the opposite.
 */
function checkDetail(c: Check): CheckDetail {
  const rev = c.polarity === "reverse";
  const w = rev ? 1 - c.rate_with : c.rate_with;
  const o = rev ? 1 - c.rate_without : c.rate_without;
  return { id: c.id, statement: c.text, line: line(c), withPct: pct(w), withoutPct: pct(o), opposite: rev, shown: true };
}

/**
 * One short line per distinct basis of a part's checks (run, questions, answers per side): the size, then whether
 * the difference with and without the part was confirmed on new questions.
 */
function basis(b: RunBundle, checks: Check[]): string[] {
  const groups = new Map<string, Check[]>();
  for (const c of checks) {
    const key = `${c.data === "confirmation" ? "c" : "m"}|${c.n_questions}|${c.n_answers}`;
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  return [...groups.values()].map((g) => {
    const size = `${g[0].n_questions} questions, ${g[0].n_answers} answers per side.`;
    const conf = g.find((c) => c.cause === "confirmed");
    if (conf) {
      const p = statementOf(b, conf)?.p;
      return `${size} Confirmed on new questions${typeof p === "number" ? `, p = ${fmtP(p)}` : ""}.`;
    }
    const ps = g.map((c) => statementOf(b, c)?.p);
    if (ps.every((p) => typeof p === "number" && p >= 0.05)) return `${size} No measurable difference.`;
    return `${size} A difference, not confirmed on new questions.`;
  });
}

/** Per answer (question, sample, arm), whether it does what the part asks; only readable verdicts. */
function doesMap(b: RunBundle, c: Check): Map<string, boolean> {
  const reverse = c.polarity === "reverse";
  const m = new Map<string, boolean>();
  const run = c.data === "confirmation" ? "c" : "m";
  for (const [q, smp, v] of statementOf(b, c)?.verdicts ?? [])
    for (const arm of [0, 1] as const) if (v[arm] === "y" || v[arm] === "n") m.set(`${run}|${q}|${smp}|${arm}`, doesWhat(v[arm], reverse));
  return m;
}

/** How often two checks agree, over the answers both were judged on (both arms), after each one's polarity. */
export function agreement(a: Map<string, boolean>, z: Map<string, boolean>): { share: number; n: number } {
  let n = 0;
  let same = 0;
  for (const [k, v] of a) {
    const w = z.get(k);
    if (w === undefined) continue;
    n++;
    if (v === w) same++;
  }
  return { share: n ? same / n : 0, n };
}

/** Fold only the same measurement: at least this agreement, and both verdicts at least this often in the earlier check. */
const FOLD_AGREE = 0.95;
const FOLD_MIN_CLASS = 3;

/**
 * Every check of a part, in order. A check that measures the same thing as an earlier one (their per-answer verdicts
 * agree on at least 95% of the answers both were judged on, and the earlier check has at least three answers of each
 * verdict, so a check that is always or never met never folds) gets no line of its own under the sentence; "More
 * detail" still lists it in its table.
 */
function checkDetails(b: RunBundle, checks: Check[]): CheckDetail[] {
  const maps = checks.map((c) => doesMap(b, c));
  const leads: number[] = [];
  return checks.map((c, i) => {
    const d = checkDetail(c);
    const lead = leads.find((j) => {
      const vals = [...maps[j].values()];
      const yes = vals.filter(Boolean).length;
      if (yes < FOLD_MIN_CLASS || vals.length - yes < FOLD_MIN_CLASS) return false;
      const ag = agreement(maps[j], maps[i]);
      return ag.n > 0 && ag.share >= FOLD_AGREE;
    });
    if (lead === undefined) leads.push(i);
    else d.shown = false;
    return d;
  });
}

// ---- the overview and one part's file ---------------------------------------------------------------------------

const partOf = (b: RunBundle, k: number): PartReadout =>
  b.readout?.parts?.find((p) => p.section === k) ?? { section: k, reading: "unclear", adherence: "not_assessed", adherence_basis: "screen" };

export function buildView(id: string): RunView {
  const b = bundle(id);
  const nConf = b.confirmation?.responses?.length ?? 0;
  const nConfQ = b.confirmation?.queries?.length ?? 0;
  const n = (x: number) => x.toLocaleString("en");
  return {
    id,
    title: b.meta.title,
    model: b.meta.model,
    lede: `${b.meta.title}. Each button says whether the model does what that part of the prompt asks.`,
    size:
      `${n(b.responses.length)} answers to ${n(b.meta.queries.length)} questions` +
      (nConf ? `, and ${n(nConf)} more to ${n(nConfQ)} new questions in a second test.` : "."),
    parts: b.sections.map((s) => {
      const p = partOf(b, s.id);
      return {
        k: s.id,
        label: s.label,
        text: s.text,
        reading: p.reading as Reading,
        side: (p.side_effects?.length ?? 0) > 0,
      } satisfies PartOverview;
    }),
  };
}

function sideOf(b: RunBundle, k: number, ids: string[]): PartFile["side"] {
  const sid = ids[0];
  if (!sid) return null;
  const cand = b.confirmation?.candidates?.find((c) => c.id === sid && c.confirmed);
  const st: Statement | undefined = cand ?? b.discovery?.statements?.find((s) => s.id === sid);
  if (!st) return null;
  const name = cap(st.label?.trim() || st.text.replace(/\.$/, ""));
  const sentence = `${name}, on other questions: ${answers(st.full_rate)} with it, ${share(st.ablated_rate)} without.`;
  const from = cand ? "confirmation" : "main";
  const v = (st.verdicts ?? []).find(([, , x]) => x === "yn") ?? (st.verdicts ?? []).find(([, , x]) => /^[yn][yn]$/.test(x));
  const get = responses(b, from);
  const a = v && get(null, v[0], v[1]);
  const z = v && get(k, v[0], v[1]);
  const question = v ? (from === "main" ? b.meta.queries[v[0]] : b.confirmation!.queries[v[0]].text) : "";
  return { sentence, pair: a && z ? { question, from, with: answer(a), without: answer(z), note: null } : null };
}

export function buildPart(id: string, k: number): PartFile {
  const b = bundle(id);
  const p = partOf(b, k);
  const lead = leadOf(p);
  const checks = checkDetails(b, p.checks ?? []);
  const ex = lead ? pairFor(b, k, lead) : null;
  let drew: PartFile["drew"] = null;
  const lift = ex && ex.pair.from === "main" ? screen(id)?.lift[String(ex.q)] : undefined;
  if (ex && lift) {
    const rows: DrewRow[] = lift
      .map((l, j) => ({ j, l: l ?? 0 }))
      .sort((a, z) => z.l - a.l)
      .slice(0, 3)
      .map(({ j, l }) => ({
        k: j,
        label: b.sections[j].label,
        first: firstLine(b.sections[j].text),
        lift: l,
        tint: l >= 2.2 ? 3 : l >= 1.6 ? 2 : 1,
      }));
    drew = { question: ex.pair.question, rows, stoodOut: rows.some((r) => r.lift >= 1.5) };
  }
  return {
    k,
    sentence: SENTENCE[p.reading as Reading] ?? SENTENCE.unclear,
    checks,
    basis: basis(b, p.checks ?? []),
    hidden: p.excluded?.length ?? 0,
    example: ex?.pair ?? null,
    drew,
    side: sideOf(b, k, p.side_effects ?? []),
  };
}
