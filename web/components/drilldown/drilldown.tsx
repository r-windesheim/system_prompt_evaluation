"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { renderAnswer } from "@/lib/markdown";
import { spring } from "@/lib/motion";
import type { Effect, Response, RunBundle } from "@/lib/types";
import { cap, f1, f2, FLAG_TEXT, noun, phrase, qText, signed } from "@/lib/words";

/*
 * The results drill-down: one thing per screen, deeper on demand.
 *   Overview (what each part does) → Part (what changes without it) → Habit (answers side by side) → Details (how sure)
 * State lives in the URL hash (#part-3, #part-3-list-item, #part-3-list-item-details) so every level is linkable.
 */

const METRIC_IDS = new Set(["words", "lines", "any_question", "ends_question", "any_list", "asks_context"]);
type Route = { level: 0 } | { level: 1; k: number } | { level: 2 | 3; k: number; d: string };
const slug = (d: string) => d.replace(/_/g, "-");

function parse(hash: string, run: Index): Route {
  const m = hash.match(/^#part-(\d+)(?:-([a-z-]+?))?(-details)?$/);
  if (!m || !run.b.sections[+m[1]]) return { level: 0 };
  const k = +m[1];
  if (!m[2]) return { level: 1, k };
  const d = m[2].replace(/-/g, "_");
  if (!run.det.has(d)) return { level: 1, k };
  return { level: m[3] ? 3 : 2, k, d };
}

type Index = ReturnType<typeof indexBundle>;
function indexBundle(b: RunBundle) {
  const det = new Map(b.detectors.map((d) => [d.id, d]));
  const isMetric = (id: string) => det.get(id)?.kind === "metric" || METRIC_IDS.has(id);
  const eff = new Map(b.effects.map((e) => [`${e.detector}|${e.section}`, e]));
  const resp = new Map(b.responses.map((r) => [`${r.config}|${r.query_idx}|${r.sample_idx}`, r]));
  const habits = (k: number) => b.effects.filter((e) => e.section === k && !isMetric(e.detector));
  return {
    b,
    det,
    isMetric,
    effect: (d: string, k: number) => eff.get(`${d}|${k}`),
    response: (cfg: string, q: number, s: number) => resp.get(`${cfg}|${q}|${s}`),
    findings: (k: number) => habits(k).filter((e) => e.significant).sort((a, z) => Math.abs(z.delta) - Math.abs(a.delta)),
    notDetected: (k: number) =>
      habits(k).filter((e) => !e.significant && e.tested !== false && !(e.flags ?? []).includes("not_testable"))
        .sort((a, z) => Math.max(z.full_mean, z.ablated_mean) - Math.max(a.full_mean, a.ablated_mean)),
    shape: (k: number) => b.effects.filter((e) => e.section === k && isMetric(e.detector) && e.significant),
  };
}

/** "61 vs 79 words" style text for a shape metric (with vs without). */
function shapeText(e: Effect): string {
  const share = noun(e.detector).startsWith("answers");
  const a = share ? `${Math.round(e.full_mean * 100)}%` : f1(e.full_mean);
  const z = share ? `${Math.round(e.ablated_mean * 100)}%` : f1(e.ablated_mean);
  return share ? `${a} vs ${z} of ${noun(e.detector)}` : `${a} vs ${z} ${noun(e.detector)}`;
}
const PART_FLAGS = ["length_shift", "context_shift"] as const;

const count = (r: Response | undefined, d: string) => (r ? r.spans.filter((s) => s.detector === d).length : 0);

export function DrillDown({ bundle }: { bundle: RunBundle }) {
  const run = useMemo(() => indexBundle(bundle), [bundle]);
  const [route, setRoute] = useState<Route>({ level: 0 });
  const dir = useRef(1);
  const reduce = useReducedMotion();
  const top = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sync = () => {
      const next = parse(location.hash, run);
      setRoute((prev) => {
        dir.current = next.level >= prev.level ? 1 : -1;
        return next;
      });
    };
    sync();
    addEventListener("hashchange", sync);
    return () => removeEventListener("hashchange", sync);
  }, [run]);

  const go = useCallback((hash: string) => {
    if (location.hash === hash) return;
    history.pushState(null, "", hash || location.pathname + location.search);
    dispatchEvent(new HashChangeEvent("hashchange"));
    top.current?.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, [reduce]);

  const key = JSON.stringify(route);
  return (
    <div ref={top} className="scroll-mt-6">
      <Crumbs run={run} route={route} go={go} />
      <AnimatePresence mode="wait" initial={false} custom={dir.current}>
        <motion.div
          key={key}
          custom={dir.current}
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: 28 * dir.current }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, x: -20 * dir.current }}
          transition={reduce ? { duration: 0.12 } : spring.layout}
        >
          {route.level === 0 && <Overview run={run} go={go} />}
          {route.level === 1 && <PartView run={run} k={route.k} go={go} />}
          {route.level === 2 && <HabitView run={run} k={route.k} d={route.d} go={go} />}
          {route.level === 3 && <DetailsView run={run} k={route.k} d={route.d} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function Crumbs({ run, route, go }: { run: Index; route: Route; go: (h: string) => void }) {
  const items: [string, string][] = [["Overview", ""]];
  if (route.level >= 1) {
    const { k } = route as { k: number };
    items.push([run.b.sections[k].label, `#part-${k}`]);
    if (route.level >= 2) {
      const { d } = route as { k: number; d: string };
      items.push([cap(noun(d)), `#part-${k}-${slug(d)}`]);
    }
    if (route.level >= 3) items.push(["How sure", ""]);
  }
  return (
    <nav aria-label="Where you are" className="mb-7 flex min-h-[22px] flex-wrap items-center gap-1.5 text-[14px] text-graphite">
      {items.map(([t, h], i) =>
        i === items.length - 1 ? (
          <span key={i} aria-current="page" className="text-ink">{t}</span>
        ) : (
          <span key={i} className="flex items-center gap-1.5">
            <button type="button" onClick={() => go(h)} className="underline decoration-rule-strong underline-offset-[3px] hover:text-ink">{t}</button>
            <span aria-hidden>›</span>
          </span>
        ),
      )}
    </nav>
  );
}

/* ---------------- level 0: what each part does ---------------- */
function Overview({ run, go }: { run: Index; go: (h: string) => void }) {
  const { b } = run;
  const warnings = b.analysis?.warnings ?? [];
  return (
    <div className="max-w-[760px]">
      <h2 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">What each part of the prompt does</h2>
      <p className="mt-2 text-[15px] text-graphite">
        Each part was taken out on its own and the same {b.meta.queries.length} questions were asked {b.meta.n_per_query} times.
        Only changes that clearly beat chance are listed. Pick a part to see more.
      </p>
      {warnings.length > 0 && (
        <ul className="mt-4 grid gap-1.5 rounded-lg border border-rule bg-sheet px-4 py-3 text-[13.5px] text-graphite">
          {warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
      <div className="mt-6 grid gap-2.5">
        {b.sections.map((s) => {
          const f = run.findings(s.id);
          const notes = s.notes ?? [];
          return (
            <motion.button
              key={s.id}
              type="button"
              whileHover={{ y: -1 }}
              transition={spring.snap}
              onClick={() => go(`#part-${s.id}`)}
              className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-xl border border-rule bg-sheet px-5 py-4 text-left hover:border-rule-strong"
            >
              <span className="font-semibold">{s.label}</span>
              <span className="row-span-3 text-[20px] text-graphite" aria-hidden>›</span>
              <span className="line-clamp-2 font-mono text-[12.5px] text-graphite">{s.text}</span>
              <span className="mt-1 text-[15px]">
                {f.length ? (
                  <>
                    Makes the model{" "}
                    {f.slice(0, 2).map((e, i) => (
                      <span key={e.detector}>
                        {i > 0 && " and "}
                        <span className={e.delta > 0 ? "text-[var(--g-structure)]" : "text-cobalt"}>{phrase(e.detector, e.delta)}</span>
                      </span>
                    ))}
                    {f.length > 2 && <span className="text-graphite">, +{f.length - 2} more</span>}
                  </>
                ) : run.shape(s.id).some((e) => e.detector === "words") ? (
                  <span>
                    Changes answer length{" "}
                    <span className="text-graphite tabular-nums">({shapeText(run.shape(s.id).find((e) => e.detector === "words")!)} with it vs without)</span>
                  </span>
                ) : notes.some((n) => n.startsWith("never tested")) ? (
                  <span className="text-graphite">Not testable with these questions</span>
                ) : (
                  <span className="text-graphite">Not detected</span>
                )}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- level 1: one part ---------------- */
function PartView({ run, k, go }: { run: Index; k: number; go: (h: string) => void }) {
  const s = run.b.sections[k];
  const f = run.findings(k);
  const nd = run.notDetected(k);
  const shape = run.shape(k);
  const [showNd, setShowNd] = useState(false);
  const max = Math.max(0.5, ...f.map((e) => Math.max(e.full_mean, e.ablated_mean)));
  const nq = run.b.meta.queries.length;
  return (
    <div className="max-w-[760px]">
      <h2 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">{s.label}</h2>
      <blockquote className="mt-3 rounded-r-lg border-l-[3px] border-cobalt bg-sheet px-4 py-3 font-mono text-[13.5px] leading-relaxed">{s.text}</blockquote>
      {(s.notes ?? []).map((n) => (
        <p key={n} className="mt-3 text-[14px] text-graphite">{cap(n)}.</p>
      ))}

      {PART_FLAGS.filter((x) => f.some((e) => (e.flags ?? []).includes(x)) && !(s.notes ?? []).some((n) => n.startsWith("context"))).map((x) => (
        <p key={x} className="mt-3 text-[14px] text-[var(--caution)]">{FLAG_TEXT[x]}</p>
      ))}
      {f.length > 0 ? (
        <>
          <p className="mt-7 mb-2.5 text-[15px] text-graphite">On these {nq} questions, because of this part the model will:</p>
          <div className="grid gap-2">
            {f.map((e) => {
              const pq = e.per_query ?? [];
              const same = pq.filter((x) => Math.sign(x) === Math.sign(e.delta)).length;
              return (
                <button
                  key={e.detector}
                  type="button"
                  onClick={() => go(`#part-${k}-${slug(e.detector)}`)}
                  className="grid w-full grid-cols-[1fr_minmax(150px,190px)_16px] items-center gap-4 rounded-xl border border-rule bg-sheet px-4 py-3.5 text-left hover:border-rule-strong max-sm:grid-cols-[1fr_16px]"
                >
                  <span>
                    <span className="block text-[16px]">{phrase(e.detector, e.delta)}</span>
                    <span className="block text-[13px] text-graphite tabular-nums">
                      {f1(e.full_mean)} {noun(e.detector)} per answer with it, {f1(e.ablated_mean)} without
                      {pq.length > 1 && ` · ${e.delta > 0 ? "higher" : "lower"} on ${same} of ${pq.length} questions`}
                    </span>
                    {(e.flags ?? []).filter((x) => x === "in_lists").map((x) => (
                      <span key={x} className="mt-1 block text-[12.5px] text-[var(--caution)]">{FLAG_TEXT[x]}</span>
                    ))}
                  </span>
                  <span className="grid gap-1 text-[12px] text-graphite max-sm:col-start-1" aria-hidden>
                    <Bar label="with" value={e.full_mean} max={max} cls="bg-ink" />
                    <Bar label="without" value={e.ablated_mean} max={max} cls="bg-cobalt" />
                  </span>
                  <span className="text-graphite" aria-hidden>›</span>
                </button>
              );
            })}
          </div>
        </>
      ) : (
        <p className="mt-7 text-[15px]">
          Taking this part out made no change we could detect. That isn&apos;t proof it does nothing: these questions may not
          exercise it, or its effect may be smaller than this run can see.
        </p>
      )}

      {shape.length > 0 && (
        <p className="mt-5 text-[14px] text-graphite tabular-nums">
          Answer shape, with this part vs without: {shape.map(shapeText).join(" · ")}.
        </p>
      )}

      {nd.length > 0 && (
        <div className="mt-5 text-[14px] text-graphite">
          {nd.length} other habits showed no detectable change.{" "}
          <button type="button" className="underline underline-offset-[3px] hover:text-ink" aria-expanded={showNd} onClick={() => setShowNd((v) => !v)}>
            {showNd ? "Hide" : "Show them"}
          </button>
          <AnimatePresence initial={false}>
            {showNd && (
              <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="mt-2 grid gap-1 overflow-hidden">
                {nd.map((e) => (
                  <li key={e.detector} className="tabular-nums">
                    {cap(noun(e.detector))}: {f1(e.full_mean)} with, {f1(e.ablated_mean)} without
                    {e.mde != null && ` (could only have spotted a change of about ${f1(e.mde)} or more)`}
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function Bar({ label, value, max, cls }: { label: string; value: number; max: number; cls: string }) {
  return (
    <span className="grid grid-cols-[48px_1fr_28px] items-center gap-2">
      <span>{label}</span>
      <span className="relative h-2 overflow-hidden rounded bg-rule">
        <motion.i className={`absolute inset-y-0 left-0 rounded ${cls}`} initial={{ width: 0 }} animate={{ width: `${(value / max) * 100}%` }} transition={spring.data} />
      </span>
      <span className="tabular-nums">{f1(value)}</span>
    </span>
  );
}

/* ---------------- level 2: answers side by side ---------------- */
function typicalCell(run: Index, k: number, d: string, e: Effect) {
  // the pair whose difference is closest to the average, preferring pairs where the habit appears at all
  const { meta } = run.b;
  let best = { q: 0, s: 0, score: Infinity };
  for (let q = 0; q < meta.queries.length; q++)
    for (let s = 0; s < meta.n_per_query; s++) {
      const a = count(run.response("full", q, s), d);
      const z = count(run.response(`without_${k}`, q, s), d);
      const score = Math.abs(a - z - e.delta) + (a + z === 0 ? 1 : 0);
      if (score < best.score) best = { q, s, score };
    }
  return { q: best.q, s: best.s };
}

function HabitView({ run, k, d, go }: { run: Index; k: number; d: string; go: (h: string) => void }) {
  const e = run.effect(d, k)!;
  const det = run.det.get(d);
  const { meta, sections } = run.b;
  const [cell, setCell] = useState(() => typicalCell(run, k, d, e));
  const [picked, setPicked] = useState(false);
  const A = run.response("full", cell.q, cell.s);
  const B = run.response(`without_${k}`, cell.q, cell.s);
  return (
    <div>
      <h2 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">{sections[k].label}: {noun(d)}</h2>
      <p className="mt-2 max-w-[72ch] text-[16px]">
        With this part the model averages <b className="tabular-nums">{f1(e.full_mean)}</b> {noun(d)} per answer. Without it,{" "}
        <b className="tabular-nums">{f1(e.ablated_mean)}</b>. Below, one question answered both ways, with the {noun(d)} highlighted.
      </p>
      <p className="mt-1 max-w-[72ch] text-[13.5px] text-graphite">
        {det?.description}{" "}
        {det?.precision != null
          ? `On ${det.precision_model} answers, ${Math.round(det.precision * 100)}% of highlights were correct (${det.precision_n} checked).`
          : "Highlight accuracy hasn't been checked on this model yet."}
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-1.5">
        {meta.queries.map((t, i) => (
          <button
            key={i}
            type="button"
            aria-pressed={i === cell.q}
            onClick={() => { setCell({ q: i, s: 0 }); setPicked(true); }}
            className={`max-w-[17rem] truncate rounded-full border px-3 py-1 text-[13px] ${i === cell.q ? "border-ink bg-ink text-paper" : "border-rule bg-sheet text-graphite hover:text-ink"}`}
          >
            {t}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-1 text-[13px] text-graphite">
          <button type="button" aria-label="Previous answer" disabled={cell.s === 0} onClick={() => { setCell((c) => ({ ...c, s: c.s - 1 })); setPicked(true); }} className="rounded px-2 py-0.5 hover:text-ink disabled:opacity-30">‹</button>
          <span className="tabular-nums">answer {cell.s + 1} of {meta.n_per_query}</span>
          <button type="button" aria-label="Next answer" disabled={cell.s >= meta.n_per_query - 1} onClick={() => { setCell((c) => ({ ...c, s: c.s + 1 })); setPicked(true); }} className="rounded px-2 py-0.5 hover:text-ink disabled:opacity-30">›</button>
        </span>
      </div>
      {!picked && <p className="mt-2 text-[12.5px] text-graphite">Showing a typical pair: its difference is the closest to the average.</p>}

      <div className="mt-3 grid overflow-hidden rounded-xl border border-rule bg-sheet md:grid-cols-2">
        <AnswerCol title={`With “${sections[k].label}”`} r={A} d={d} q={meta.queries[cell.q]} />
        <AnswerCol title="Without it" r={B} d={d} q={meta.queries[cell.q]} without />
      </div>
      <p className="mt-2 text-[12.5px] text-graphite">
        Both answers come from separate samples of the model. The comparison across all {e.n_pairs} pairs is the evidence, not this one pair.
      </p>
      <button type="button" onClick={() => go(`#part-${k}-${slug(d)}-details`)} className="mt-5 text-[14px] text-graphite underline underline-offset-[3px] hover:text-ink">
        How sure are we? See the details
      </button>
    </div>
  );
}

function AnswerCol({ title, r, d, q, without }: { title: string; r?: Response; d: string; q: string; without?: boolean }) {
  const html = useMemo(() => (r ? renderAnswer(r.text, r.spans, d) : ""), [r, d]);
  return (
    <div className={`min-w-0 px-5 pt-4 pb-5 ${without ? "border-rule max-md:border-t md:border-l" : ""}`}>
      <div className="mb-2.5 flex justify-between gap-3 text-[13px] text-graphite">
        <span className={without ? "text-cobalt" : ""}>{title}</span>
        <span className="tabular-nums">
          <span className="inline-block min-w-[1.6em] rounded bg-[var(--mark)] px-1.5 text-center font-semibold text-[var(--mark-ink)]">{count(r, d)}</span> {noun(d)}
        </span>
      </div>
      <p className="mb-2 text-[13.5px] text-graphite">User: <b className="font-medium text-ink">{q}</b></p>
      {r?.finish_reason === "length" && <p className="mb-2 text-[12.5px] text-[var(--g-framing)]">This answer was cut off and is left out of the numbers.</p>}
      <div className="answer" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

/* ---------------- level 3: how sure ---------------- */
function DetailsView({ run, k, d }: { run: Index; k: number; d: string }) {
  const e = run.effect(d, k)!;
  const { meta, analysis } = run.b;
  const rows: [string, React.ReactNode][] = [
    ["With this part", `${f2(e.full_mean)} ${noun(d)} per answer`],
    ["Without it", `${f2(e.ablated_mean)} per answer`],
    ["Difference", `${signed(e.delta, 2)} per answer`],
    ["Plausible range", `${f2(e.ci[0])} to ${f2(e.ci[1])} (average over these ${e.n_pairs} pairs, 95%)`],
  ];
  if (e.ci_query) rows.push(["If the questions varied", `${f2(e.ci_query[0])} to ${f2(e.ci_query[1])} (treating each question as one sample, 95%)`]);
  rows.push(["Expected false findings", `${qText(e.q)} of findings at this cutoff would be false (q-value across ${analysis?.n_tests ?? "all"} tests)`]);
  if (e.mde != null) rows.push(["Smallest visible change", `about ${f2(e.mde)} per answer; anything smaller would likely be missed`]);
  return (
    <div className="max-w-[760px]">
      <h2 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">How sure are we?</h2>
      <p className="mt-1 text-graphite">{run.b.sections[k].label} → {noun(d)}</p>
      <dl className="mt-5 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2.5 text-[15px] tabular-nums max-sm:grid-cols-1">
        {rows.map(([a, b]) => (
          <div key={a} className="contents">
            <dt className="text-graphite">{a}</dt>
            <dd>{b}</dd>
          </div>
        ))}
      </dl>
      {(e.per_query?.length ?? 0) > 1 && (
        <>
          <h3 className="mt-8 text-[15px] font-semibold">Per question</h3>
          <ul className="mt-2 grid gap-1.5 text-[14px] tabular-nums">
            {e.per_query!.map((x, i) => (
              <li key={i} className="grid grid-cols-[1fr_70px] gap-3">
                <span className="text-graphite">{meta.queries[i]}</span>
                <span className={x === 0 ? "text-graphite" : ""}>{signed(x, 2)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-8 grid gap-2.5 text-[14.5px] text-graphite">
        <p><b className="text-ink">How it was measured.</b> Each part was taken out one at a time, and the same questions were asked again. A difference counts only if it beats chance after correcting for testing every part against every habit.</p>
        <p><b className="text-ink">What it can&apos;t tell you.</b> A highlighted phrase matched the {noun(d)} detector. That doesn&apos;t prove this part caused that phrase. Parts are removed one at a time, so two parts that ask for the same thing can hide each other. The result describes these {meta.queries.length} questions on {meta.model}.</p>
        {(e.flags ?? []).filter((x) => x !== "not_testable").map((x) => <p key={x}><b className="text-ink">Caution.</b> {FLAG_TEXT[x]}</p>)}
      </div>
    </div>
  );
}
