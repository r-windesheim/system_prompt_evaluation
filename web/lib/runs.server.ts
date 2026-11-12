import "server-only";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { RunBundle, RunSummary } from "./types";

const RUNS_DIR = path.join(process.cwd(), "public", "runs");

export function runIds(): string[] {
  return readdirSync(RUNS_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(/\.json$/, ""))
    .sort();
}

export function loadRun(id: string): RunBundle {
  return JSON.parse(readFileSync(path.join(RUNS_DIR, `${id}.json`), "utf8")) as RunBundle;
}

export function summarize(b: RunBundle): RunSummary {
  const det = new Map(b.detectors.map((d) => [d.id, d.label]));
  const sec = new Map(b.sections.map((s) => [s.id, s.label]));
  return {
    meta: b.meta,
    sections: b.sections.map(({ id, label }) => ({ id, label })),
    nResponses: b.responses.length,
    top: b.effects
      .filter((e) => e.significant)
      .sort((a, z) => Math.abs(z.delta) - Math.abs(a.delta))
      .slice(0, 6)
      .map((e) => ({
        detector: e.detector,
        detectorLabel: det.get(e.detector) ?? e.detector,
        section: e.section,
        sectionLabel: sec.get(e.section) ?? `Section ${e.section + 1}`,
        delta: e.delta,
        q: e.q,
      })),
  };
}

export function allSummaries(): RunSummary[] {
  return runIds()
    .map((id) => summarize(loadRun(id)))
    .sort((a, z) => Number(a.meta.fixture) - Number(z.meta.fixture) || z.meta.created_at.localeCompare(a.meta.created_at));
}
