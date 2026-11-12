// Accessibility (axe), reduced-motion and frame-budget checks against the static export.
// Usage: node scripts/audit.mjs [baseUrl]   (needs: npm i -D playwright @axe-core/playwright --no-save)
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const base = process.argv[2] ?? "http://localhost:3101";
const browser = await chromium.launch({ headless: true });
let fail = 0;

for (const scheme of ["light", "dark"]) {
  for (const path of ["/", "/run/?id=lumen-original-probes", "/run/?id=lumen-original-probes#part-3", "/run/?id=lumen-original-probes#part-3-list-item", "/run/?id=lumen-original-probes#part-3-list-item-details", "/analyze/", "/method/"]) {
    const page = await (await browser.newContext({ colorScheme: scheme, viewport: { width: 1440, height: 1000 } })).newPage();
    await page.goto(base + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
    console.log(`axe ${scheme.padEnd(5)} ${path.padEnd(18)} ${bad.length} serious/critical, ${r.violations.length - bad.length} minor`);
    for (const v of r.violations) console.log(`   - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}) e.g. ${v.nodes[0]?.target}`);
    fail += bad.length;
    await page.close();
  }
}

// Frame budget while moving through the drill-down (4x CPU throttle)
{
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
  await page.goto(base + "/run/?id=lumen-original-probes", { waitUntil: "networkidle" });
  await page.waitForSelector("text=What each part of the prompt does");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.evaluate(() => {
    window.__frames = [];
    let last = performance.now();
    const tick = (t) => { window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  for (const step of ["part", "habit", "details", "back", "back", "back"]) {
    if (step === "part") await page.getByRole("button", { name: /Step Formatting/ }).first().click();
    if (step === "habit") await page.locator("main button", { hasText: "bullet points" }).first().click();
    if (step === "details") await page.getByRole("button", { name: /How sure are we/ }).click();
    if (step === "back") await page.goBack();
    await page.waitForTimeout(700);
  }
  const f = await page.evaluate(() => window.__frames.slice(2));
  f.sort((a, b) => a - b);
  const p = (q) => f[Math.floor(q * (f.length - 1))].toFixed(1);
  console.log(`frames (4x CPU throttle): n=${f.length} p50=${p(0.5)}ms p95=${p(0.95)}ms max=${f.at(-1).toFixed(1)}ms, >50ms: ${f.filter((x) => x > 50).length}`);
  await page.close();
}

// Reduced motion: level changes must not slide (no transforms mid-transition)
{
  const page = await (await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 1000 } })).newPage();
  await page.goto(base + "/run/?id=lumen-original-probes", { waitUntil: "networkidle" });
  await page.waitForSelector("text=What each part of the prompt does");
  await page.getByRole("button", { name: /Step Formatting/ }).first().click();
  await page.waitForTimeout(40);
  const moved = await page.evaluate(() => [...document.querySelectorAll("main div")].filter((el) => {
    const t = getComputedStyle(el).transform; return t && t !== "none" && !/matrix\(1, 0, 0, 1, 0, 0\)/.test(t);
  }).length);
  console.log(`reduced motion: elements mid-slide 40ms after navigating: ${moved}`);
  await page.close();
}

await browser.close();
process.exit(fail ? 1 : 0);
