import "server-only";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { CLAUSES, type ClauseCopy } from "./view-copy";
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

const copyOf = (id: string, c: Check): ClauseCopy => CLAUSES[id]?.[c.id] ?? { clause: c.text.replace(/^The answer\s+/i, "").replace(/\.$/, "") };

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
/** An answer that says it cannot open something, or asks for the text, is a decline, not a made-up answer. */
const DECLINES = /\b(can(?:no|['’])t|unable|not able|don['’]t have (?:the ability|access)|no (?:way|ability) to|paste)\b/i;

function responses(b: RunBundle, from: "main" | "confirmation") {
  const list = from === "main" ? b.responses : b.confirmation?.responses ?? [];
  const cfg = new Map<number | null, string>(from === "main" ? b.configs.map((c) => [c.removed, c.id]) : []);
  const m = new Map(list.map((r) => [`${r.config}|${r.query_idx}|${r.sample_idx}`, r]));
  const name = (removed: number | null) => (from === "main" ? cfg.get(removed) : removed === null ? "full" : `without_${removed}`);
  return (removed: number | null, q: number, s: number) => m.get(`${name(removed)}|${q}|${s}`);
}

function pairFor(id: string, b: RunBundle, k: number, c: Check): { pair: Pair; q: number } | null {
  const pick = pickPair(b, c);
  if (!pick) return null;
  const from = c.data === "confirmation" ? "confirmation" : "main";
  const get = responses(b, from);
  const a = get(null, pick.q, pick.s);
  const z = get(k, pick.q, pick.s);
  if (!a || !z) return null;
  const question = from === "main" ? b.meta.queries[pick.q] : b.confirmation!.queries[pick.q].text;
  const copy = copyOf(id, c);
  let note: Pair["note"] = null;
  if (copy.unread) {
    const sides: ["with" | "without", Response, string][] = [["without", z, pick.v[1]], ["with", a, pick.v[0]]];
    const hit = sides.find(([, r, v]) => !doesWhat(v, pick.reverse) && !DECLINES.test(r.text));
    if (hit) note = { side: hit[0], text: copy.unread };
  }
  return { pair: { question, from, with: answer(a), without: answer(z), note }, q: pick.q };
}

// ---- words for a part -----------------------------------------------------------------------------------------

const DOES: Record<Check["does"], string> = { mostly: "mostly", sometimes: "sometimes", rarely: "rarely", unclear: "unclear" };

function line(id: string, c: Check): string {
  return `${cap(copyOf(id, c).clause)}: ${DOES[c.does]} (${share(c.rate_with)} of the answers with this part, ${share(c.rate_without)} without it).`;
}

/** Removing the part changed nothing measurable: every check's paired by-question p is at least 0.05. */
function noMeasurableChange(b: RunBundle, checks: Check[]): boolean | null {
  const ps = checks.map((c) => statementOf(b, c)?.p);
  if (!ps.length || ps.some((p) => typeof p !== "number")) return null;
  return ps.every((p) => (p as number) >= 0.05);
}

function sentence(b: RunBundle, p: PartReadout): string {
  const checks = p.checks ?? [];
  const same = noMeasurableChange(b, checks);
  const removed =
    same === true
      ? " Removing the part did not measurably change how often it does this."
      : same === false
        ? " Answers without the part differed, but that was not confirmed on new questions."
        : "";
  switch (p.reading as Reading) {
    case "followed": {
      const nq = checks.find((c) => c.cause === "confirmed")?.n_questions;
      return `Yes, and this part is the reason: without it, the model does this less often, and a second test on ${nq ? `${nq} ` : ""}new questions confirmed the difference.`;
    }
    case "does_it":
      return same === true
        ? "Mostly, yes. But removing the part did not measurably change how often it does this, so the part is not shown to be the reason."
        : `Mostly, yes, but the part is not shown to be the reason.${removed}`;
    case "not_needed":
      return `Yes, but it does this anyway: answers without the part do it too.${removed}`;
    case "partly_followed":
      return `Partly. It does some of what this part asks, or does it only some of the time.${removed}`;
    case "not_followed":
      return `No. Even with this part, the model rarely does this.${removed}`;
    default:
      return "Unclear. The checks for this part could not tell either way.";
  }
}

const SOURCE: Record<Check["data"], string> = {
  confirmation: "from the second test, on new questions",
  screen: "from the main run, on the questions written for this part",
  authored: "from the main run, with a statement written from the part’s text before any answer was read",
};
const fmtP = (p: number) => (p < 0.001 ? "below 0.001" : p < 0.01 ? p.toFixed(3) : p.toFixed(2));

function checkDetail(id: string, b: RunBundle, c: Check): CheckDetail {
  const s = statementOf(b, c);
  const notes = [`${c.n_questions} questions, ${c.n_answers} answers on each side, ${SOURCE[c.data]}.`];
  if (c.rate_with_ci) notes.push(`With this part, by question: ${pct(c.rate_with_ci[0])} to ${pct(c.rate_with_ci[1])}.`);
  if (typeof s?.p === "number")
    notes.push(`Difference with and without, tested by question: p = ${fmtP(s.p)}${c.cause === "confirmed" ? ", confirmed" : ""}.`);
  if (s?.measure) notes.push("Counted by word count, not by the judge.");
  if (c.polarity === "reverse") notes.push("The part asks for the opposite of this statement, so an answer counts where the judge said no.");
  if ((c.flags ?? []).includes("rejudge_one_class"))
    notes.push("The judge gave the same verdict to every answer it read twice, so whether it could say the opposite was not tested.");
  if ((c.flags ?? []).includes("too_few_questions")) notes.push("Few of the questions applied.");
  return { id: c.id, statement: c.text, line: line(id, c), withPct: pct(c.rate_with), withoutPct: pct(c.rate_without), notes, shown: true };
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
 * detail" still lists it and says which statement it agreed with.
 */
function checkDetails(id: string, b: RunBundle, checks: Check[]): CheckDetail[] {
  const ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"];
  const maps = checks.map((c) => doesMap(b, c));
  const leads: number[] = [];
  return checks.map((c, i) => {
    const d = checkDetail(id, b, c);
    const lead = leads.find((j) => {
      const vals = [...maps[j].values()];
      const yes = vals.filter(Boolean).length;
      if (yes < FOLD_MIN_CLASS || vals.length - yes < FOLD_MIN_CLASS) return false;
      const ag = agreement(maps[j], maps[i]);
      return ag.n > 0 && ag.share >= FOLD_AGREE;
    });
    if (lead === undefined) leads.push(i);
    else {
      const ag = agreement(maps[lead], maps[i]);
      d.shown = false;
      d.notes.push(
        `This check and the ${ORD[lead] ?? `number ${lead + 1}`} statement in this table agreed on ${ag.share === 1 ? "every" : "nearly every"} answer (${pct(ag.share)} of ${ag.n}), so they share one line under the sentence.`,
      );
    }
    return d;
  });
}

function deep(b: RunBundle, p: PartReadout): string[] {
  const checks = p.checks ?? [];
  const out: string[] = [];
  const judged = checks.filter((c) => !statementOf(b, c)?.measure);
  if (judged.length)
    out.push(
      `A judge, the same small model (${String(b.meta.settings?.judge_model ?? b.meta.model).split("/").pop()}), read each answer on its own, without knowing which prompt wrote it, and said whether each statement holds. ` +
        "It often answers no where a statement does not apply to the question.",
    );
  else if (checks.length) out.push("These checks are word counts, so no judge was involved.");
  const conf = checks.find((c) => c.cause === "confirmed");
  if (conf)
    out.push(`The difference was seen in the main run first, then tested again on ${conf.n_questions} new questions whose answers the first run never saw.`);
  if (p.reading === "not_followed" || p.reading === "not_needed")
    out.push("This reading rests on how often the judge says yes, not on a difference between the two sides, so it is less certain than “followed”.");
  if (checks.length === 1) out.push("The reading rests on one check.");
  const n = p.excluded?.length ?? 0;
  if (n)
    out.push(
      `${cap(n === 1 ? "one other statement" : `${n} other statements`)} written for this part ${n === 1 ? "was" : "were"} left out: a review found ${n === 1 ? "it" : "them"} not matching the part, or the judge unsteady on ${n === 1 ? "it" : "them"}.`,
    );
  return out;
}

// ---- the overview and one part's file ---------------------------------------------------------------------------

export const LEDES: Record<string, string> = {
  "sonnet35-july2024":
    "The system prompt Anthropic published for Claude 3.5 Sonnet in July 2024, tested on a different, small open model, gpt-oss-20b. Each button says whether the model does what that part asks.",
};

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
    lede: LEDES[id] ?? `${b.meta.title}. Each button says whether the model does what that part asks.`,
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
  const clause = st.text.replace(/^The answer\s+/i, "").replace(/\.$/, "");
  const sentence = `On questions about other things, it ${clause} in ${share(st.full_rate)} of the answers, against ${share(st.ablated_rate)} without this part.`;
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
  const ex = lead ? pairFor(id, b, k, lead) : null;
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
    sentence: sentence(b, p),
    checks: checkDetails(id, b, p.checks ?? []),
    deep: deep(b, p),
    example: ex?.pair ?? null,
    drew,
    side: sideOf(b, k, p.side_effects ?? []),
  };
}
