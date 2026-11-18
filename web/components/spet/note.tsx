"use client";

import { motion, useReducedMotion } from "motion/react";
import type { Run } from "@/lib/run";
import { arrive as arriveAt, instant } from "@/lib/motion";

export function Chevron() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** What a part changes, in the margin: a button with a short name. Everything else is inside the opened part. */
export function ResultNote({ run, k, i, open, id }: { run: Run; k: number; i: number; open: boolean; id: string }) {
  const reduce = useReducedMotion();
  const n = run.note(k);
  return (
    <motion.div className="note" id={id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={reduce ? { ...instant, delay: 0 } : arriveAt(i)}>
      <span className={`pill ${n.kind}`}>
        {n.says}
        <Chevron />
      </span>
    </motion.div>
  );
}
