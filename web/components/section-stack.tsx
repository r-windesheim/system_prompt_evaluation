"use client";

import { AnimatePresence, motion } from "motion/react";
import { groupColor } from "@/lib/groups";
import { spring } from "@/lib/motion";
import type { RunIndex } from "@/lib/use-run";

type Props = {
  run: RunIndex;
  removed: number | null;
  onToggle: (k: number) => void;
};

export function SectionStack({ run, removed, onToggle }: Props) {
  const { sections } = run.bundle;
  return (
    <div>
      <h2 className="text-[13px] text-graphite">System prompt</h2>
      <p className="mt-1 mb-4 text-[13px] text-graphite">
        Remove one section to see the same conversations without it.
      </p>
      <ol className="flex flex-col">
        {sections.map((s) => {
          const off = removed === s.id;
          const drives = run.significantFor(s.id).filter((e) => e.delta > 0);
          return (
            <motion.li layout key={s.id} className="relative border-t border-rule last:border-b">
              <button
                type="button"
                aria-pressed={off}
                aria-label={`${off ? "Restore" : "Remove"} section: ${s.label}`}
                onClick={() => onToggle(s.id)}
                className="group relative block w-full py-2.5 pr-2 pl-4 text-left lg:py-3"
              >
                {/* the ablation rail: grows in cobalt when the section is removed */}
                <motion.span
                  aria-hidden
                  className="absolute top-0 bottom-0 left-0 w-[3px] origin-top rounded-full bg-cobalt"
                  initial={false}
                  animate={{ scaleY: off ? 1 : 0, opacity: off ? 1 : 0 }}
                  transition={spring.snap}
                />
                <span className="flex items-baseline justify-between gap-3">
                  <motion.span
                    layout="position"
                    className={`text-[14px] font-medium ${off ? "text-cobalt line-through decoration-1" : "text-ink"}`}
                  >
                    {s.label}
                  </motion.span>
                  <span className="flex shrink-0 items-center gap-1" aria-hidden>
                    {drives.slice(0, 4).map((e) => (
                      <span
                        key={e.detector}
                        className="size-[7px] rounded-full"
                        style={{ background: groupColor(run.detectors.get(e.detector)?.group ?? "") }}
                      />
                    ))}
                    <span className="ml-2 text-[12px] text-graphite opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                      {off ? "Restore" : "Remove"}
                    </span>
                  </span>
                </span>
                <AnimatePresence initial={false}>
                  {!off && (
                    <motion.span
                      key="text"
                      className="block overflow-hidden"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={spring.layout}
                    >
                      <span className="block pt-1.5 font-mono text-[12.5px] leading-[1.6] text-graphite max-lg:hidden">
                        {s.text}
                      </span>
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
