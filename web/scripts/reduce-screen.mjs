// Reduce an attention screen file to what the viewer shows: per question, each part's reasoning-token lift.
// Usage (from web/): node scripts/reduce-screen.mjs <run-id> <screen.json>
//   e.g. node scripts/reduce-screen.mjs sonnet35-july2024 ../runs_out/sonnet35-july2024-screen.json
// Writes data/screens/<run-id>.json. The screen must be the one the run's discovery used (sha256 checked), so the
// build never depends on runs_out/ and the page never shows a screen made for other questions.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const [id, file] = process.argv.slice(2);
if (!id || !file) {
  console.error("usage: node scripts/reduce-screen.mjs <run-id> <screen.json>");
  process.exit(2);
}
const raw = readFileSync(file);
const sha = createHash("sha256").update(raw).digest("hex");
const bundle = JSON.parse(readFileSync(path.join("public", "runs", `${id}.json`), "utf8"));
const want = bundle.discovery?.screen?.sha256;
if (want && want !== sha) {
  console.error(`screen sha256 ${sha} does not match the run's discovery.screen.sha256 ${want}`);
  process.exit(1);
}
const s = JSON.parse(raw);
const nParts = bundle.sections.length;
if (s.part_labels.length !== nParts || s.n_questions !== bundle.meta.queries.length) {
  console.error("screen parts or questions do not match the run");
  process.exit(1);
}
const lift = {};
for (const p of s.pairs) {
  const l = p.reasoning?.lift;
  if (typeof l !== "number") continue;
  (lift[p.query_idx] ??= Array(nParts).fill(null))[p.section] = Math.round(l * 100) / 100;
}
const out = { run: id, sha256: sha, block: "reasoning", model: s.model, n_samples: s.n_samples, lift };
mkdirSync(path.join("data", "screens"), { recursive: true });
const dest = path.join("data", "screens", `${id}.json`);
writeFileSync(dest, JSON.stringify(out));
console.log(`wrote ${dest}: ${Object.keys(lift).length} questions, ${readFileSync(dest).length} bytes`);
