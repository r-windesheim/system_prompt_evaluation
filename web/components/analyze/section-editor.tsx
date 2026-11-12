"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { SectionDraft } from "@/lib/api";
import { instant, spring } from "@/lib/motion";

/**
 * The prompt as one continuous document. Every gap between two paragraphs is a
 * switch: on = a section break, off = the paragraphs belong to the same section.
 * Sections are the runs of paragraphs between breaks, each with an editable label.
 */

function labelFrom(text: string): string {
  const t = text.trim();
  const h = t.match(/^\s*#{1,6}\s+(.+)$/m);
  if (h) return h[1].trim().slice(0, 48);
  const x = t.match(/^\s*<([A-Za-z_][\w-]*)/);
  if (x) return (x[1][0].toUpperCase() + x[1].slice(1)).replace(/[_-]/g, " ").slice(0, 48);
  const words = t.replace(/\s+/g, " ").split(" ");
  return (words.slice(0, 5).join(" ") + (words.length > 5 ? "…" : "")).slice(0, 48);
}

function atomize(sections: SectionDraft[]): { atoms: string[]; breaks: boolean[] } {
  const atoms: string[] = [];
  const breaks: boolean[] = [];
  sections.forEach((s, si) => {
    const parts = s.text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    parts.forEach((p, pi) => {
      if (atoms.length) breaks.push(pi === 0 && si > 0);
      atoms.push(p);
    });
  });
  return { atoms, breaks };
}

export function SectionEditor({
  initial,
  onChange,
}: {
  initial: SectionDraft[];
  onChange: (sections: SectionDraft[]) => void;
}) {
  const reduce = useReducedMotion();
  const start = useMemo(() => atomize(initial), [initial]);
  const [breaks, setBreaks] = useState<boolean[]>(start.breaks);
  // labels keyed by the index of the group's first paragraph, so they survive toggling elsewhere
  const [labels, setLabels] = useState<Record<number, string>>(() => {
    const out: Record<number, string> = {};
    let a = 0;
    for (const s of initial) {
      out[a] = s.label;
      a += s.text.split(/\n\s*\n/).filter((p) => p.trim()).length;
    }
    return out;
  });
  const atoms = start.atoms;

  const groups = useMemo(() => {
    const gs: { start: number; atoms: number[] }[] = [{ start: 0, atoms: [0] }];
    for (let i = 1; i < atoms.length; i++) {
      if (breaks[i - 1]) gs.push({ start: i, atoms: [i] });
      else gs[gs.length - 1].atoms.push(i);
    }
    return gs;
  }, [atoms.length, breaks]);

  const groupOf = useMemo(() => {
    const m: number[] = [];
    groups.forEach((g, gi) => g.atoms.forEach((a) => (m[a] = gi)));
    return m;
  }, [groups]);

  useEffect(() => {
    onChange(
      groups.map((g) => ({
        label: (labels[g.start] ?? labelFrom(atoms[g.start])).trim() || labelFrom(atoms[g.start]),
        text: g.atoms.map((a) => atoms[a]).join("\n\n"),
      })),
    );
  }, [groups, labels, atoms, onChange]);

  const toggle = (i: number) => setBreaks((b) => b.map((v, j) => (j === i ? !v : v)));
  const setAll = (v: boolean) => setBreaks((b) => b.map(() => v));
  const t = reduce ? instant : spring.layout;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-graphite">
        <span className="tabular-nums text-ink">
          {groups.length} section{groups.length === 1 ? "" : "s"} from {atoms.length} paragraph{atoms.length === 1 ? "" : "s"}
        </span>
        <button type="button" className="hover:text-ink" onClick={() => setAll(true)}>Every paragraph its own section</button>
        <button type="button" className="hover:text-ink" onClick={() => setAll(false)}>Clear all breaks</button>
      </div>

      <div className="rounded-lg border border-rule bg-sheet px-5 py-4">
        {atoms.map((text, i) => {
          const gi = groupOf[i];
          const isStart = groups[gi].start === i;
          return (
            <div key={i}>
              {i > 0 && <Gap on={breaks[i - 1]} onToggle={() => toggle(i - 1)} index={i} />}
              <AnimatePresence initial={false}>
                {isStart && (
                  <motion.div
                    key="head"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={t}
                    className="overflow-hidden"
                  >
                    <div className="flex items-center gap-3 pt-1 pb-2">
                      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-ink text-[12px] text-paper tabular-nums">
                        {gi + 1}
                      </span>
                      <label htmlFor={`sec-label-${i}`} className="sr-only">Section {gi + 1} label</label>
                      <input
                        id={`sec-label-${i}`}
                        value={labels[i] ?? labelFrom(text)}
                        onChange={(e) => setLabels((l) => ({ ...l, [i]: e.target.value }))}
                        className="w-full max-w-[28rem] rounded-md border border-transparent bg-transparent px-2 py-1 text-[14.5px] font-medium hover:border-rule focus:border-cobalt focus:bg-paper focus:outline-none"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              <motion.p
                layout="position"
                transition={t}
                className="ml-3 border-l-2 border-rule py-1 pl-6 font-mono text-[13px] leading-[1.7] whitespace-pre-wrap text-ink"
              >
                {text}
              </motion.p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Gap({ on, onToggle, index }: { on: boolean; onToggle: () => void; index: number }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`Section break before paragraph ${index + 1}`}
      onClick={onToggle}
      className="group my-1 flex w-full items-center gap-3 rounded-md py-1.5 text-left"
    >
      <span
        className={`relative inline-flex h-[16px] w-[28px] shrink-0 items-center rounded-full border transition-colors ${
          on ? "border-ink bg-ink" : "border-rule-strong bg-paper group-hover:border-graphite"
        }`}
      >
        <motion.span
          className={`absolute size-[10px] rounded-full ${on ? "bg-paper" : "bg-rule-strong group-hover:bg-graphite"}`}
          initial={false}
          animate={{ left: on ? 14 : 2 }}
          transition={spring.snap}
        />
      </span>
      <span className={`h-px flex-1 transition-colors ${on ? "bg-ink" : "bg-transparent group-hover:bg-rule"}`} style={on ? undefined : { backgroundImage: "linear-gradient(90deg, var(--rule) 50%, transparent 50%)", backgroundSize: "8px 1px" }} />
      <span className={`text-[12px] transition-opacity ${on ? "text-ink" : "text-graphite opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"}`}>
        {on ? "Section break" : "Split here"}
      </span>
    </button>
  );
}
