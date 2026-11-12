"use client";

import { motion } from "motion/react";
import { spring } from "@/lib/motion";

/** Dot-and-whisker on a symmetric axis [-max, max]. Zero is the centre line. */
export function EffectBar({
  delta,
  ci,
  max,
  color,
  significant,
}: {
  delta: number;
  ci: [number, number];
  max: number;
  color: string;
  significant: boolean;
}) {
  const x = (v: number) => `${50 + (Math.max(-max, Math.min(max, v)) / max) * 50}%`;
  const lo = 50 + (Math.max(-max, ci[0]) / max) * 50;
  const hi = 50 + (Math.min(max, ci[1]) / max) * 50;
  return (
    <div className="relative h-4 w-full" aria-hidden>
      <div className="absolute top-1/2 right-0 left-0 h-px -translate-y-1/2 bg-rule" />
      <div className="absolute top-0 bottom-0 left-1/2 w-px bg-rule-strong" />
      <motion.div
        className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full"
        style={{ background: color, opacity: significant ? 0.9 : 0.35 }}
        initial={{ left: "50%", width: "0%" }}
        animate={{ left: `${lo}%`, width: `${Math.max(0.6, hi - lo)}%` }}
        transition={spring.data}
      />
      <motion.div
        className="absolute top-1/2 size-[9px] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background: significant ? color : "var(--sheet)",
          boxShadow: `0 0 0 1.5px ${color}`,
          opacity: significant ? 1 : 0.55,
        }}
        initial={{ left: "50%" }}
        animate={{ left: x(delta) }}
        transition={spring.data}
      />
    </div>
  );
}
