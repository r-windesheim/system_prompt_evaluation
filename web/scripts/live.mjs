// The live flow against a `spet serve` backed by the mock model (never a paid endpoint):
//   SPET_BASE_URL=http://localhost:8001/v1 SPET_MODEL=mock SPET_API_KEY=x python -m spet serve --port 8002 --runs-dir <tmp>
//   NEXT_PUBLIC_SPET_API=http://localhost:8002 npm run build, then serve out/ (e.g. on 3112).
// Usage: node scripts/live.mjs <outDir> [baseUrl] [apiUrl]
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://localhost:3112";
const apiUrl = process.argv[4] ?? "http://localhost:8002";
mkdirSync(out, { recursive: true });
const health = await (await fetch(`${apiUrl}/api/health`)).json();
if (health.model !== "mock") throw new Error(`refusing to run: ${apiUrl} is not backed by the mock model (${health.model})`);

const PROMPT = `You are the support assistant for Acme, a hosting company.

Always apologise when the user reports a problem, even if it is not our fault.

Be humble about uncertainty and avoid overstating what you know.

Use bullet points for any steps the user should follow.

Be warm and encouraging toward the user.`;

const browser = await chromium.launch({ headless: true });
const errors = [];
const calls = [];
const hosts = new Set();
let fail = 0;
const check = (ok, msg) => { console.log(`${ok ? "ok  " : "FAIL"} ${msg}`); if (!ok) fail++; };

for (const [w, viewport] of [["1440", { width: 1440, height: 900 }], ["390", { width: 390, height: 844 }]]) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2, hasTouch: w === "390" });
  const p = await ctx.newPage();
  p.on("console", (m) => m.type() === "error" && errors.push(`${w}: ${m.text()}`));
  p.on("pageerror", (e) => errors.push(`${w}: ${e.message}`));
  p.on("request", (r) => { hosts.add(new URL(r.url()).host); if (r.url().includes("/api/")) calls.push(`${r.method()} ${new URL(r.url()).pathname}`); });
  await p.goto(base + "/", { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);

  // the unchanged example never calls the model
  calls.length = 0;
  await p.getByRole("button", { name: "Split into parts" }).click();
  await p.waitForSelector("button[role=switch]");
  check(!calls.some((c) => c.includes("/api/split")), `${w}: the unchanged example is split locally, without the model`);
  await p.getByRole("button", { name: "Edit the text" }).click();

  // a pasted prompt goes through the real splitter and a real run
  await p.getByRole("button", { name: "Clear it to paste your own" }).click();
  await p.locator("textarea#prompt").fill(PROMPT);
  check(await p.getByText("Your prompt").isVisible(), `${w}: a changed prompt is labelled as the visitor's own`);
  await p.getByRole("button", { name: "Split into parts" }).click();
  await p.waitForSelector("button[role=switch]");
  check(calls.includes("POST /api/split"), `${w}: splitting a pasted prompt calls /api/split`);
  const parts = (await p.locator("button[role=switch][aria-checked=true]").count()) + 1;
  check(parts >= 2, `${w}: the pasted prompt is split into ${parts} parts`);
  await p.getByRole("button", { name: "See the questions" }).click();
  await p.getByRole("button", { name: "Concrete tasks" }).click();
  // the samples field can be typed into: "1" is allowed mid-typing, "15" stays 15
  await p.locator("#n-edit").click({ clickCount: 3 });
  await p.keyboard.type("15");
  check((await p.locator("#n-edit").inputValue()) === "15", `${w}: typing 15 into the samples field gives 15`);
  check(await p.getByText(`${((parts + 1) * 5 * 15).toLocaleString("en")} answers in all`).isVisible(), `${w}: the options show how many answers the run asks for`);
  await p.waitForTimeout(300);
  await p.mouse.move(0, 0);
  await p.screenshot({ path: `${out}/live-2-parts-options-${w}.png` });
  {
    const r = await new AxeBuilder({ page: p }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
    for (const v of r.violations) console.log(`   - [${v.impact}] ${v.id}: ${v.help} e.g. ${v.nodes[0]?.target}`);
    check(!bad.length, `${w}: axe finds no serious violations with the run options open`);
  }
  // a run long enough to watch: 20 questions (unique per pass, so nothing is served from cache), 40 times each
  const stamp = Date.now();
  const qs = Array.from({ length: 20 }, (_, i) => `Question ${i + 1} of pass ${stamp}-${w}: my deploy fails, what should I check?`);
  await p.locator("#qs-edit").fill(qs.join("\n"));
  await p.locator("#n-edit").click({ clickCount: 3 });
  await p.keyboard.type("40");
  await p.locator("#n-edit").blur();

  await p.getByRole("button", { name: new RegExp(`^Test ${parts} parts$`) }).click();
  await p.waitForSelector('.comp[data-phase="running"]');
  check(calls.includes("POST /api/runs"), `${w}: Test starts a run`);
  // watch the real progress: a part struck with a partly filled bar, earlier parts marked tested, the line advancing
  await p.waitForSelector(".row.out", { timeout: 30000 });
  await p.waitForSelector(".says.done", { timeout: 30000 });
  const sample = () => p.evaluate(() => ({
    line: parseFloat(document.querySelector(".progress i")?.style.width ?? "0"),
    bars: [...document.querySelectorAll(".row.out .bar i")].map((i) => parseFloat(i.style.width)),
    out: document.querySelectorAll(".row.out").length,
    done: document.querySelectorAll(".says.done").length,
    lede: document.querySelector(".lede")?.textContent,
  }));
  const s1 = await sample();
  await p.mouse.move(0, 0);
  await p.screenshot({ path: `${out}/live-3-running-${w}.png` });
  await p.waitForTimeout(1200);
  const s2 = await sample();
  console.log(`     ${w} mid-run: ${JSON.stringify(s1)} then ${JSON.stringify(s2)}`);
  check(s1.out >= 1 && s1.bars.some((b) => b > 0 && b < 100), `${w}: a part being tested is struck, with a partly filled bar`);
  check(s1.done >= 1, `${w}: parts already tested say so`);
  check(s2.line > s1.line, `${w}: the progress line advances (${s1.line.toFixed(1)}% to ${s2.line.toFixed(1)}%)`);
  check(/^Testing part \d+ of \d+/.test(s1.lede ?? ""), `${w}: the lede names the part being tested`);
  await p.waitForSelector(".row.result", { timeout: 120000 });
  check(calls.some((c) => /\/api\/runs\/.+\/status/.test(c)), `${w}: progress comes from the status endpoint`);
  const url = new URL(p.url());
  check(url.pathname.endsWith("/run/") && !!url.searchParams.get("id"), `${w}: the finished run's address is in the bar (${url.pathname}${url.search})`);
  await p.waitForTimeout(900);
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.screenshot({ path: `${out}/live-4-result-${w}.png` });
  const found = await p.locator(".row.result.found").count();
  check(found >= 3, `${w}: the planted habits are found (${found} parts with a finding)`);
  await p.locator(".row.result.found .text-btn").nth(1).click();
  await p.waitForSelector(".detail .pair");
  await p.waitForTimeout(500);
  await p.locator(".row.open").evaluate((el) => el.scrollIntoView({ block: "start" }));
  await p.screenshot({ path: `${out}/live-5-open-${w}.png` });

  // the saved run opens on its own
  const id = url.searchParams.get("id");
  const q = await (await browser.newContext({ viewport })).newPage();
  q.on("console", (m) => m.type() === "error" && errors.push(`${w} saved: ${m.text()}`));
  await q.goto(`${base}/run/?id=${id}#part=2`, { waitUntil: "networkidle" });
  await q.waitForSelector("#detail-2", { timeout: 15000 }).catch(() => {});
  check(await q.locator("#detail-2").isVisible(), `${w}: /run/?id=${id}#part=2 opens the saved live run with part 2 open`);
  await ctx.close();
}

await browser.close();
check(!hosts.has("localhost:8000"), `no request went to the paid API on 8000 (hosts: ${[...hosts].join(", ")})`);
console.log(errors.length ? "CONSOLE ERRORS:\n" + errors.join("\n") : "no console errors");
console.log(fail ? `${fail} check(s) failed` : "all checks passed");
process.exit(fail || errors.length ? 1 : 0);
