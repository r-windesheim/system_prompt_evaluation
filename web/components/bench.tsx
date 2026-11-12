"use client";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { groupColor } from "@/lib/groups";
import type { RunIndex } from "@/lib/use-run";
import { EffectsPanel } from "./effects-panel";
import { DiffText, MatchedText } from "./response-text";
import { SectionStack } from "./section-stack";

export type BenchState = {
  removed: number | null;
  query: number;
  sample: number;
  focus: string | null;
};

type Props = {
  run: RunIndex;
  state: BenchState;
  setState: (fn: (s: BenchState) => BenchState) => void;
};

export function Bench({ run, state, setState }: Props) {
  const { meta } = run.bundle;
  const { removed, query, sample, focus } = state;
  const full = run.response(null, query, sample);
  const ablated = removed !== null ? run.response(removed, query, sample) : undefined;
  const set = (patch: Partial<BenchState>) => setState((s) => ({ ...s, ...patch }));
  const toggle = (k: number) => setState((s) => ({ ...s, removed: s.removed === k ? null : k }));

  return (
    <LayoutGroup>
      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-[minmax(250px,300px)_minmax(0,1fr)_minmax(270px,320px)]">
        <SectionStack run={run} removed={removed} onToggle={toggle} />

        <section aria-label="Response" className="min-w-0">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[13px] text-graphite">Conversation</h2>
            <div className="flex items-center gap-1 text-[13px] text-graphite">
              <button
                type="button"
                aria-label="Previous sample"
                className="rounded px-1.5 hover:text-ink disabled:opacity-30"
                disabled={sample === 0}
                onClick={() => set({ sample: sample - 1 })}
              >
                ‹
              </button>
              <span className="tnum">
                Sample {sample + 1} of {meta.n_per_query}
              </span>
              <button
                type="button"
                aria-label="Next sample"
                className="rounded px-1.5 hover:text-ink disabled:opacity-30"
                disabled={sample >= meta.n_per_query - 1}
                onClick={() => set({ sample: sample + 1 })}
              >
                ›
              </button>
            </div>
          </div>

          <div role="tablist" aria-label="User message" className="-mx-1 mt-3 flex gap-1 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [mask-image:linear-gradient(to_right,black_88%,transparent)]">
            {meta.queries.map((q, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={i === query}
                title={q}
                onClick={() => set({ query: i })}
                className={`relative isolate max-w-[13rem] shrink-0 truncate rounded-full px-3 py-1 text-[12.5px] ${i === query ? "text-paper" : "text-graphite hover:text-ink"}`}
              >
                {i === query && (
                  <motion.span layoutId="query-pill" className="absolute inset-0 -z-10 rounded-full bg-ink" />
                )}
                {q}
              </button>
            ))}
          </div>

          <div className="mt-5 rounded-lg border border-rule bg-sheet">
            <p className="border-b border-rule px-5 py-3 text-[14px]">
              <span className="sr-only">User: </span>
              {meta.queries[query]}
            </p>
            <div className="px-5 py-4">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={`${removed}-${query}-${sample}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.12 }}
                >
                  {full && ablated ? (
                    <DiffText full={full} ablated={ablated} />
                  ) : full ? (
                    <MatchedText run={run} response={full} focus={focus} />
                  ) : (
                    <p className="text-graphite">This configuration has no response for this cell.</p>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <Legend run={run} diff={removed !== null} focus={focus} />
        </section>

        <EffectsPanel
          run={run}
          removed={removed}
          focus={focus}
          onFocus={(d) => set({ focus: d })}
          onRemove={(k) => set({ removed: k })}
        />
      </div>
    </LayoutGroup>
  );
}

function Legend({ run, diff, focus }: { run: RunIndex; diff: boolean; focus: string | null }) {
  if (diff)
    return (
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-graphite">
        <span>
          <span className="w-del">struck</span> only with the section
        </span>
        <span>
          <span className="w-ins">marked</span> only without it
        </span>
        <span>Same conversation, same sampling seed.</span>
      </p>
    );
  const groups = [...new Set(run.bundle.detectors.map((d) => d.group))];
  return (
    <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-graphite">
      <span>Underlines mark detector matches, not causes.</span>
      {groups.map((g) => (
        <span key={g} className="inline-flex items-center gap-1.5">
          <span className="h-[2px] w-3 rounded-full" style={{ background: groupColor(g) }} />
          {g}
        </span>
      ))}
      {focus && <span className="text-ink">Showing {run.detectors.get(focus)?.label}</span>}
    </p>
  );
}
