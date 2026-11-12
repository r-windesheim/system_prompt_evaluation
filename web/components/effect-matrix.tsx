"use client";

import { motion } from "motion/react";
import { fmtDelta, fmtQ, groupColor } from "@/lib/groups";
import { spring } from "@/lib/motion";
import type { RunIndex } from "@/lib/use-run";

/** Detectors × sections. Filled = significant increase, ring = significant decrease, faint = not significant. */
export function EffectMatrix({
  run,
  removed,
  focus,
  onPick,
}: {
  run: RunIndex;
  removed: number | null;
  focus: string | null;
  onPick: (k: number, d: string) => void;
}) {
  const { sections, detectors } = run.bundle;
  const rows = detectors.filter((d) => sections.some((s) => (run.effect(d.id, s.id)?.full_mean ?? 0) > 0 || (run.effect(d.id, s.id)?.ablated_mean ?? 0) > 0));
  const size = (v: number) => 6 + Math.min(1, Math.abs(v) / run.maxAbs) * 18;

  return (
    <section aria-labelledby="matrix-h">
      <h2 id="matrix-h" className="text-[17px] font-semibold tracking-tight">
        Every section against every quirk
      </h2>
      <p className="mt-1 max-w-[62ch] text-[14px] text-graphite">
        Dot size is the change in matches per response. Filled dots are significant increases, rings are significant
        decreases, faint dots didn&apos;t pass correction. Select one to open it above.
      </p>
      <div className="mt-6 overflow-x-auto">
        <table className="border-separate border-spacing-0 text-[13px]">
          <thead>
            <tr>
              <th className="sticky left-0 bg-paper" />
              {sections.map((s) => (
                <th
                  key={s.id}
                  scope="col"
                  className={`h-28 w-14 align-bottom font-normal ${removed === s.id ? "text-cobalt" : "text-graphite"}`}
                >
                  <span className="inline-block origin-bottom-left translate-x-[18px] -rotate-45 whitespace-nowrap">{s.label}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <th scope="row" className={`sticky left-0 bg-paper py-1 pr-4 text-left font-normal whitespace-nowrap ${focus === d.id ? "text-ink" : "text-graphite"}`}>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-[7px] rounded-full" style={{ background: groupColor(d.group) }} />
                    {d.label}
                  </span>
                </th>
                {sections.map((s) => {
                  const e = run.effect(d.id, s.id);
                  if (!e) return <td key={s.id} />;
                  const c = groupColor(d.group);
                  const px = size(e.delta);
                  const pos = e.delta > 0;
                  const active = removed === s.id && focus === d.id;
                  return (
                    <td key={s.id} className={`h-9 w-14 text-center ${removed === s.id ? "bg-cobalt-wash/50" : ""}`}>
                      <button
                        type="button"
                        onClick={() => onPick(s.id, d.id)}
                        aria-label={`${d.label} × ${s.label}: ${fmtDelta(e.delta)} per response, ${fmtQ(e.q)}${e.significant ? ", significant" : ""}`}
                        title={`${fmtDelta(e.delta)} · ${fmtQ(e.q)}`}
                        className={`inline-grid size-8 place-items-center rounded-md ${active ? "ring-2 ring-cobalt" : "hover:bg-sheet"}`}
                      >
                        <motion.span
                          className="block rounded-full"
                          initial={false}
                          animate={{ width: px, height: px }}
                          transition={spring.data}
                          style={
                            e.significant
                              ? pos
                                ? { background: c }
                                : { boxShadow: `inset 0 0 0 2px ${c}` }
                              : { background: c, opacity: 0.16, width: 6, height: 6 }
                          }
                        />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
