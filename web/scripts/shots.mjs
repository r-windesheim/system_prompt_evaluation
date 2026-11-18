// First-viewport screenshots of every state, at 1440x900 and 390x844, plus a scripted pass through the example.
// Usage: node scripts/shots.mjs <outDir> [baseUrl] [nameFilter]
//   baseUrl: a static server over a build made WITHOUT NEXT_PUBLIC_SPET_API (the example path needs no model).
// Never point this at a dev server whose API reaches a paid model: it clicks "Split" and "Test".
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://localhost:3101";
const only = process.argv[4] ? new RegExp(process.argv[4]) : null;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const errors = [];
let fail = 0;
const check = (ok, msg) => { console.log(`${ok ? "ok  " : "FAIL"} ${msg}`); if (!ok) fail++; };

const sizes = [["1440", { width: 1440, height: 900 }], ["390", { width: 390, height: 844 }]];

async function page(viewport, url, opts = {}) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2, hasTouch: viewport.width < 500, ...opts });
  const p = await ctx.newPage();
  p.on("console", (m) => m.type() === "error" && errors.push(`${url} ${viewport.width}: ${m.text()}`));
  p.on("pageerror", (e) => errors.push(`${url} ${viewport.width}: ${e.message}`));
  await p.goto(base + url, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  return { ctx, p };
}
const snap = async (p, name) => {
  if (only && !only.test(name)) return;
  await p.mouse.move(0, 0);
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${out}/${name}.png` });
};
const toTop = (p) => p.evaluate(() => window.scrollTo(0, 0));

for (const [w, viewport] of sizes) {
  // the example, through all five states
  const { ctx, p } = await page(viewport, "/");
  check(await p.locator("textarea#prompt").isVisible(), `${w}: state 1 shows the editable prompt`);
  await snap(p, `1-start-${w}`);
  await p.getByRole("button", { name: "Split into parts" }).click();
  await p.waitForSelector("button[role=switch]");
  check((await p.locator("button[role=switch][aria-checked=true]").count()) === 6, `${w}: state 2 splits the example into 7 parts`);
  await snap(p, `2-parts-${w}`);
  // merge two parts: the example can no longer be tested without a model; restore it
  await p.locator("button[role=switch]").nth(2).click();
  check(await p.getByRole("button", { name: "Test 6 parts" }).isDisabled(), `${w}: a changed split cannot be tested without a model`);
  check(await p.getByText("Testing anything else needs a model connected").isVisible(), `${w}: says only the example can be tested`);
  if (w === "1440") await snap(p, `2b-merged-no-model-${w}`);
  await p.locator("button[role=switch]").nth(2).click();
  check(!(await p.getByRole("button", { name: "Test 7 parts" }).isDisabled()), `${w}: splitting again re-enables Test`);
  await p.getByRole("button", { name: "See the questions" }).click();
  check(await p.getByText("“This seems wrong”").isVisible(), `${w}: the questions disclosure lists the questions`);
  await p.getByRole("button", { name: "Hide the questions" }).click();
  await p.getByRole("button", { name: "Test 7 parts" }).click();
  await p.waitForTimeout(760 * 4 + 300);
  check((await p.locator(".row.out").count()) === 1, `${w}: state 3 strikes one part at a time`);
  await snap(p, `3-running-${w}`);
  await p.waitForSelector(".row.result", { timeout: 15000 });
  check((await p.getByText("Example result, recorded earlier").count()) === 1, `${w}: the result says it is the example's saved result`);
  await p.waitForTimeout(800);
  await toTop(p);
  await snap(p, `4-result-${w}`);
  if (w === "1440" && (!only || only.test(`4b-hover-${w}`))) {
    await p.locator("#part-4").hover();
    await p.waitForTimeout(400);
    await p.screenshot({ path: `${out}/4b-hover-${w}.png` });
  }
  await p.locator("#part-4 .text-btn").click();
  await p.waitForSelector("#detail-4 .pair");
  check((await p.evaluate(() => location.hash)) === "#part=4", `${w}: opening a part puts it in the URL hash`);
  await p.locator("#part-4").evaluate((el) => el.scrollIntoView({ block: "start" }));
  await snap(p, `5-open-${w}`);
  await p.getByRole("button", { name: "More detail" }).click();
  await p.waitForTimeout(500);
  await p.locator("#detail-4 .deep").evaluate((el) => el.scrollIntoView({ block: "center" }));
  await snap(p, `5b-more-detail-${w}`);
  await p.getByRole("button", { name: "Close", exact: true }).click();
  await p.waitForTimeout(100);
  check((await p.evaluate(() => location.hash)) === "", `${w}: closing clears the hash`);
  await ctx.close();
}

// deep links and the other pages
const views = [
  ["6-no-change-open", "/#part=3"],
  ["7-untestable-open", "/#part=7"],
  ["8-saved-run", "/runs/lumen-original-probes/"],
  ["8b-saved-run-by-id", "/run/?id=lumen-original-probes"],
  ["9-stub-demo", "/run/?id=stub-demo"],
  ["9b-stub-demo-open", "/run/?id=stub-demo#part=6"],
  ["10-runs", "/runs/"],
  ["11-method", "/method/"],
];
for (const [name, url] of views) {
  for (const [w, viewport] of sizes) {
    if (only && !only.test(`${name}-${w}`)) continue;
    const { ctx, p } = await page(viewport, url);
    if (url.includes("run")) await p.waitForSelector(".row.result").catch(() => {});
    if (url.includes("#part")) {
      const n = url.match(/part=(\d+)/)[1];
      await p.waitForTimeout(400);
      check(await p.locator(`#detail-${n}`).isVisible().catch(() => false), `${w}: ${url} opens part ${n} straight away`);
    }
    await snap(p, `${name}-${w}`);
    await ctx.close();
  }
}

// a changed prompt with no model: said at once, in state 1
{
  const { ctx, p } = await page({ width: 1440, height: 900 }, "/");
  await p.locator("textarea#prompt").fill("You are a pirate.\n\nAnswer in rhymes.");
  check(await p.getByText("Without a model connected, only the example can be tested.").isVisible(), "state 1 says at once that only the example can be tested");
  await snap(p, "1b-changed-no-model-1440");
  await ctx.close();
}

await browser.close();
console.log(errors.length ? "CONSOLE ERRORS:\n" + errors.join("\n") : "no console errors");
console.log(fail ? `${fail} check(s) failed` : "all checks passed");
process.exit(fail || errors.length ? 1 : 0);
