"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { fmtDelta, fmtQ, groupColor } from "@/lib/groups";
import { instant, spring } from "@/lib/motion";
import type { Effect } from "@/lib/types";
import type { RunIndex } from "@/lib/use-run";
import { EffectBar } from "./effect-bar";

type Props = {
  run: RunIndex;
  removed: number | null;
  focus: string | null;
  onFocus: (d: string | null) => void;
  onRemove: (k: number) => void;
};

export function EffectsPanel({ run, removed, focus, onFocus, onRemove }: Props) {
  return (
    <div aria-live="polite">
      <AnimatePresence mode="wait" initial={false}>
        {removed === null ? (
          <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <Overview run={run} onRemove={onRemove} />
          </motion.div>
        ) : (
          <motion.div key="section" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            <SectionEffects run={run} k={removed} focus={focus} onFocus={onFocus} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Overview({ run, onRemove }: { run: RunIndex; onRemove: (k: number) => void }) {
  const rows = run.bundle.sections
    .map((s) => ({ s, effects: run.significantFor(s.id) }))
    .filter((r) => r.effects.length);
  const inert = run.bundle.sections.filter((s) => !run.significantFor(s.id).length);
  return (
    <div>
      <h2 className="text-[13px] text-graphite">What each section changes</h2>
      <p className="mt-1 mb-4 text-[13px] text-graphite">
        Significant effects only (q &lt; 0.05 after correcting for every test in this run).
      </p>
      <ul className="flex flex-col gap-3">
        {rows.map(({ s, effects }) => (
          <li key={s.id}>
            <button type="button" onClick={() => onRemove(s.id)} className="w-full rounded-md p-2 -m-2 text-left hover:bg-sheet">
              <span className="text-[14px] font-medium">{s.label}</span>
              <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                {effects.map((e) => {
                  const d = run.detectors.get(e.detector)!;
                  return (
                    <span key={e.detector} className="inline-flex items-center gap-1.5 text-[13px] text-graphite">
                      <span className="size-[7px] rounded-full" style={{ background: groupColor(d.group) }} />
                      {d.label}
                      <span className="tnum text-ink">{fmtDelta(e.delta)}</span>
                    </span>
                  );
                })}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {inert.length > 0 && (
        <p className="mt-5 border-t border-rule pt-3 text-[13px] text-graphite">
          No measurable effect: {inert.map((s) => s.label).join(", ")}.
        </p>
      )}
    </div>
  );
}

function SectionEffects({ run, k, focus, onFocus }: { run: RunIndex; k: number; focus: string | null; onFocus: (d: string | null) => void }) {
  const [showAll, setShowAll] = useState(false);
  const reduce = useReducedMotion();
  const all = (run.bySection.get(k) ?? []).filter((e) => e.full_mean > 0 || e.ablated_mean > 0);
  const sig = all.filter((e) => e.significant);
  const rest = all.filter((e) => !e.significant);
  const label = run.bundle.sections[k]?.label;
  return (
    <div>
      <h2 className="text-[13px] text-graphite">
        Effect of <span className="text-cobalt">{label}</span>
      </h2>
      <p className="mt-1 mb-4 text-[13px] text-graphite">
        Matches per response with the section, minus without it. Dot = mean of {all[0]?.n_pairs ?? 0} paired
        conversations, line = 95% CI.
      </p>
      {sig.length === 0 && <p className="mb-3 text-[14px]">Removing this section changed nothing measurably.</p>}
      <ul className="flex flex-col">
        {sig.map((e) => (
          <EffectRow key={e.detector} run={run} e={e} focus={focus} onFocus={onFocus} />
        ))}
      </ul>
      {rest.length > 0 && (
        <div className="mt-3">
          <button type="button" className="text-[13px] text-graphite underline-offset-4 hover:underline" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
            {showAll ? "Hide" : "Show"} {rest.length} non-significant
          </button>
          <AnimatePresence initial={false}>
            {showAll && (
              <motion.ul className="flex flex-col overflow-hidden" initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} transition={reduce ? instant : spring.layout}>
                {rest.map((e) => (
                  <EffectRow key={e.detector} run={run} e={e} focus={focus} onFocus={onFocus} />
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function EffectRow({ run, e, focus, onFocus }: { run: RunIndex; e: Effect; focus: string | null; onFocus: (d: string | null) => void }) {
  const d = run.detectors.get(e.detector)!;
  const color = groupColor(d.group);
  const active = focus === e.detector;
  return (
    <motion.li layout="position" transition={spring.layout} className="border-t border-rule first:border-t-0">
      <button
        type="button"
        aria-pressed={active}
        onClick={() => onFocus(active ? null : e.detector)}
        className={`grid w-full grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-md px-2 py-2 text-left ${active ? "bg-sheet" : "hover:bg-sheet"}`}
      >
        <span className="flex items-center gap-1.5 text-[13.5px]">
          <span className="size-[7px] rounded-full" style={{ background: color }} />
          {d.label}
          {d.precision === null && <span className="text-[11.5px] text-graphite">(precision unmeasured)</span>}
        </span>
        <span className={`tnum text-[13.5px] ${e.significant ? "text-ink" : "text-graphite"}`}>{fmtDelta(e.delta)}</span>
        <span className="col-span-2">
          <EffectBar delta={e.delta} ci={e.ci} max={run.maxAbs} color={color} significant={e.significant} />
        </span>
        <span className="tnum col-span-2 text-[12px] text-graphite">
          {e.full_mean.toFixed(2)} with, {e.ablated_mean.toFixed(2)} without · CI [{fmtDelta(e.ci[0])}, {fmtDelta(e.ci[1])}] · {fmtQ(e.q)}
        </span>
      </button>
    </motion.li>
  );
}
