"use client";

import { MotionConfig } from "motion/react";
import { spring } from "@/lib/motion";

export function Providers({ children }: { children: React.ReactNode }) {
  // "user": honour prefers-reduced-motion. Transforms and layout animations are
  // dropped, opacity changes are kept.
  return (
    <MotionConfig reducedMotion="user" transition={spring.layout}>
      {children}
    </MotionConfig>
  );
}
