// Runs the result view on bundles the showcase never exercises, served by intercepting the bundle request
// (nothing is written to public/runs). Usage: node scripts/edge-cases.mjs <outDir> [baseUrl]
//   v1        schema v1: no kind/tested/flags/per_query/ci_query/mde/notes/analysis, renamed config ids
//   nofind    nothing significant anywhere
//   negative  parts that reduce a habit ("cuts …")
//   big       12 parts, one of them several paragraphs long, 2 questions, 3 samples
import { chromium } from "playwright";
import { mkdirSync, readFileSync } from "node:fs";

const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://localhost:3100";
mkdirSync(out, { recursive: true });
const load = (id) => JSON.parse(readFileSync(new URL(`../public/runs/${id}.json`, import.meta.url), "utf8"));
const clone = (x) => JSON.parse(JSON.stringify(x));

const variants = {};
{
  const b = clone(load("lumen-original-probes"));
  b.schema_version = 1;
  b.meta.id = "edge-v1";
  delete b.meta.settings;
  b.analysis = null;
  for (const d of b.detectors) { delete d.kind; delete d.precision_model; }
  for (const s of b.sections) delete s.notes;
  for (const e of b.effects) for (const k of ["tested", "ci_query", "per_query", "mde", "flags"]) delete e[k];
  const ren = (id) => (id === "full" ? "all" : id.replace("without_", "drop-"));
  for (const c of b.configs) c.id = ren(c.id);
  for (const r of b.responses) { r.config = ren(r.config); delete r.finish_reason; }
  variants["edge-v1"] = b;
}
{
  const b = clone(load("stub-demo"));
  b.meta.id = "edge-nofind";
  b.meta.title = "Nothing found";
  for (const e of b.effects) e.significant = false;
  variants["edge-nofind"] = b;
}
{
  const b = clone(load("lumen-original-probes"));
  b.meta.id = "edge-negative";
  b.meta.title = "Instructions that reduce habits";
  const flip = (k, d, full, abl) => {
    const e = b.effects.find((x) => x.section === k && x.detector === d);
    Object.assign(e, { full_mean: full, ablated_mean: abl, delta: full - abl, ci: [full - abl - 0.3, full - abl + 0.3], q: 0.004, p: 0.001, significant: true, tested: true, flags: [] });
  };
  flip(2, "question", 1.1, 2.6); // Uncertainty Handling cuts questions back
  flip(4, "sympathy", 0.05, 0.6); // Follow-up Prompt cuts sympathy lines
  variants["edge-negative"] = b;
}
{
  const src = load("stub-demo");
  const b = clone(src);
  b.meta.id = "edge-big";
  b.meta.title = "Twelve instructions, two questions, three samples";
  b.meta.queries = src.meta.queries.slice(0, 2);
  b.meta.n_per_query = 3;
  const N = 12;
  b.sections = Array.from({ length: N }, (_, i) => ({ ...src.sections[i % 7], id: i, label: `${src.sections[i % 7].label}${i >= 7 ? " (copy)" : ""}`, notes: i === 6 ? src.sections[6].notes : [] }));
  b.sections[9].text = "First line of a longer instruction.\nSecond line, which the file view numbers separately.\n\nA third paragraph after a blank line.";
  b.configs = [{ id: "full", removed: null }, ...b.sections.map((s) => ({ id: `without_${s.id}`, removed: s.id }))];
  const keep = (r) => r.query_idx < 2 && r.sample_idx < 3;
  const full = src.responses.filter((r) => r.config === "full" && keep(r));
  b.responses = [...full];
  for (const s of b.sections) for (const r of src.responses.filter((r) => r.config === `without_${s.id % 7}` && keep(r))) b.responses.push({ ...r, config: `without_${s.id}` });
  b.effects = b.sections.flatMap((s) => src.effects.filter((e) => e.section === s.id % 7).map((e) => ({ ...e, section: s.id, per_query: e.per_query?.slice(0, 2), n_pairs: 6 })));
  variants["edge-big"] = b;
}

const browser = await chromium.launch({ headless: true });
const errors = [];
let fail = 0;
const check = (ok, msg) => { console.log(`${ok ? "ok  " : "FAIL"} ${msg}`); if (!ok) fail++; };
for (const [id, bundle] of Object.entries(variants)) {
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } });
    await ctx.route(new RegExp(`(/api/runs/${id}$|/runs/${id}\\.json$)`), (route) => route.fulfill({ json: bundle }));
    const page = await ctx.newPage();
    page.on("console", (m) => m.type() === "error" && errors.push(`${id} ${w}: ${m.text()}`));
    page.on("pageerror", (e) => errors.push(`${id} ${w}: ${e.message}`));
    await page.goto(`${base}/run/?id=${id}`, { waitUntil: "networkidle" });
    await page.waitForSelector(".row.result");
    await page.waitForTimeout(900);
    const n = await page.locator(".row.result").count();
    check(n === bundle.sections.length, `${id} ${w}: all ${n} parts shown`);
    // notes never overlap one another
    const boxes = await page.locator(".row.result .note").evaluateAll((els) => els.map((e) => e.getBoundingClientRect()).map((r) => [r.top, r.bottom]));
    const overlap = boxes.some((b, i) => i > 0 && b[0] < boxes[i - 1][1] - 1);
    check(!overlap, `${id} ${w}: margin notes do not overlap`);
    if (id === "edge-nofind") check((await page.locator(".says.found").count()) === 0, `${id} ${w}: nothing is stated as a finding`);
    if (id === "edge-negative") check((await page.getByText("cuts", { exact: false }).count()) > 0, `${id} ${w}: a reduction reads "cuts …"`);
    await page.screenshot({ path: `${out}/${id}-${w}.png`, fullPage: true });
    // every part opens, including ones with nothing to show
    for (let i = 1; i <= n; i++) {
      await page.locator(`#part-${i} .text-btn`).click();
      await page.waitForSelector(`#detail-${i}`);
      await page.getByRole("button", { name: "More detail" }).click();
      await page.waitForTimeout(80);
      const text = await page.locator(`#detail-${i}`).innerText();
      if (!text.trim().length) check(false, `${id} ${w}: part ${i} opens to an explanation`);
      if (/no effect/i.test(text)) check(false, `${id} ${w}: part ${i} never says "no effect"`);
    }
    await ctx.close();
  }
}
await browser.close();
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console errors");
console.log(fail ? `${fail} check(s) failed` : "all checks passed");
process.exit(errors.length || fail ? 1 : 0);
