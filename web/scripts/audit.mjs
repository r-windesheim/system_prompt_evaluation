// Accessibility (axe), reduced-motion and frame-budget checks against the static export.
// Usage: node scripts/audit.mjs [baseUrl]   (needs: npm i -D playwright @axe-core/playwright --no-save)
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const base = process.argv[2] ?? "http://localhost:3101";
const browser = await chromium.launch({ headless: true });
let fail = 0;

for (const scheme of ["light", "dark"]) {
  for (const path of ["/", "/runs/stub-demo/", "/method/"]) {
    const page = await (await browser.newContext({ colorScheme: scheme, viewport: { width: 1440, height: 1000 } })).newPage();
    await page.goto(base + path, { waitUntil: "networkidle" });
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
    console.log(`axe ${scheme.padEnd(5)} ${path.padEnd(18)} ${bad.length} serious/critical, ${r.violations.length - bad.length} minor`);
    for (const v of r.violations) console.log(`   - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}) e.g. ${v.nodes[0]?.target}`);
    fail += bad.length;
    await page.close();
  }
}

// Frame budget while toggling sections (4x CPU throttle)
{
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
  await page.goto(base + "/runs/stub-demo/", { waitUntil: "networkidle" });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.evaluate(() => {
    window.__frames = [];
    let last = performance.now();
    const tick = (t) => { window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  for (const label of ["Apology policy", "Formatting", "Voice", "Voice"]) {
    const name = new RegExp(`(Remove|Restore) section: ${label}`);
    await page.getByRole("button", { name }).click();
    await page.waitForTimeout(700);
  }
  const f = await page.evaluate(() => window.__frames.slice(2));
  f.sort((a, b) => a - b);
  const p = (q) => f[Math.floor(q * (f.length - 1))].toFixed(1);
  const long = f.filter((x) => x > 50).length;
  console.log(`frames (4x CPU throttle): n=${f.length} p50=${p(0.5)}ms p95=${p(0.95)}ms max=${f.at(-1).toFixed(1)}ms, >50ms: ${long}`);
  await page.close();
}

// Reduced motion: no transform animations should run on toggle
{
  const page = await (await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 1000 } })).newPage();
  await page.goto(base + "/runs/stub-demo/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Remove section: Formatting" }).click();
  const snap = () => page.evaluate(() => [...document.querySelectorAll("ol > li")].map((el) => el.getBoundingClientRect().height.toFixed(1) + "|" + el.getBoundingClientRect().top.toFixed(1)));
  await page.waitForTimeout(30);
  const a = await snap();
  await page.waitForTimeout(800);
  const b = await snap();
  const moving = a.length === b.length ? a.filter((x, i) => x !== b[i]).length : -1;
  const blurred = await page.evaluate(() => [...document.querySelectorAll(".w-del,.w-ins")].filter((e) => getComputedStyle(e).filter !== "none" && getComputedStyle(e).filter !== "blur(0px)").length);
  console.log(`reduced motion: section rows still moving 30ms→830ms after toggle: ${moving}; blurred diff words: ${blurred}`);
  await page.close();
}

await browser.close();
process.exit(fail ? 1 : 0);
