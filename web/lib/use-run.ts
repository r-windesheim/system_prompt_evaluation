"use client";

import { useMemo } from "react";
import type { Detector, Effect, Response, RunBundle } from "./types";

export type RunIndex = ReturnType<typeof indexRun>;

export function indexRun(b: RunBundle) {
  const responses = new Map<string, Response>();
  for (const r of b.responses) responses.set(`${r.config}|${r.query_idx}|${r.sample_idx}`, r);
  const detectors = new Map<string, Detector>(b.detectors.map((d) => [d.id, d]));
  const effects = new Map<string, Effect>(b.effects.map((e) => [`${e.detector}|${e.section}`, e]));
  const bySection = new Map<number, Effect[]>();
  for (const e of b.effects) {
    const list = bySection.get(e.section) ?? [];
    list.push(e);
    bySection.set(e.section, list);
  }
  for (const list of bySection.values())
    list.sort((a, z) => Number(z.significant) - Number(a.significant) || Math.abs(z.delta) - Math.abs(a.delta));
  const maxAbs = Math.max(0.5, ...b.effects.map((e) => Math.max(Math.abs(e.ci[0]), Math.abs(e.ci[1]))));
  const configFor = (removed: number | null) => (removed === null ? "full" : `without_${removed}`);
  return {
    bundle: b,
    detectors,
    effects,
    bySection,
    maxAbs,
    response: (removed: number | null, q: number, s: number) => responses.get(`${configFor(removed)}|${q}|${s}`),
    effect: (d: string, k: number) => effects.get(`${d}|${k}`),
    significantFor: (k: number) => (bySection.get(k) ?? []).filter((e) => e.significant),
  };
}

export function useRunIndex(b: RunBundle) {
  return useMemo(() => indexRun(b), [b]);
}
