"use client";

import { MotionConfig } from "motion/react";

export function Providers({ children }: { children: React.ReactNode }) {
  // "user": honour prefers-reduced-motion. Transforms and layout animations are dropped.
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
