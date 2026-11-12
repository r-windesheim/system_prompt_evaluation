"use client";

import { motion } from "motion/react";
import { useMemo } from "react";
import { wordDiff } from "@/lib/diff";
import { groupColor } from "@/lib/groups";
import { wordDelay } from "@/lib/motion";
import type { Response } from "@/lib/types";
import type { RunIndex } from "@/lib/use-run";

/** A response with detector matches underlined. Observation only: no section attribution. */
export function MatchedText({ run, response, focus }: { run: RunIndex; response: Response; focus: string | null }) {
  const segments = useMemo(() => {
    const t = response.text;
    const cuts = new Set([0, t.length]);
    for (const s of response.spans) cuts.add(s.start).add(s.end);
    const pts = [...cuts].sort((a, b) => a - b);
    const out: { text: string; dets: string[] }[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [a, b] = [pts[i], pts[i + 1]];
      const dets = response.spans.filter((s) => s.start <= a && s.end >= b).map((s) => s.detector);
      out.push({ text: t.slice(a, b), dets });
    }
    return out;
  }, [response]);

  return (
    <p className="font-mono text-[13.5px] leading-[1.75] whitespace-pre-wrap">
      {segments.map((seg, i) => {
        if (!seg.dets.length) return <span key={i}>{seg.text}</span>;
        const det = (focus && seg.dets.includes(focus) ? focus : seg.dets[0])!;
        const d = run.detectors.get(det);
        return (
          <span
            key={i}
            className="match"
            data-dim={focus !== null && !seg.dets.includes(focus)}
            title={seg.dets.map((x) => run.detectors.get(x)?.label ?? x).join(", ")}
            style={{ ["--c" as string]: groupColor(d?.group ?? "") }}
          >
            {seg.text}
          </span>
        );
      })}
    </p>
  );
}

/** Word diff from the full-prompt response to the same cell without section k. */
export function DiffText({ full, ablated }: { full: Response; ablated: Response }) {
  const ops = useMemo(() => wordDiff(full.text, ablated.text), [full.text, ablated.text]);
  let changed = 0;
  return (
    <p className="font-mono text-[13.5px] leading-[1.75] whitespace-pre-wrap">
      {ops.map((op, i) => {
        if (op.kind === "same") return <span key={i}>{op.text}</span>;
        const delay = wordDelay(changed++);
        return (
          <motion.span
            key={i}
            className={op.kind === "del" ? "w-del" : "w-ins"}
            initial={{ opacity: 0, filter: "blur(3px)" }}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            transition={{ duration: 0.28, delay }}
          >
            {op.text}
          </motion.span>
        );
      })}
    </p>
  );
}
