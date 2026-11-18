// Accessibility (axe) on every state and page, and a reduced-motion check.
// Usage: node scripts/audit.mjs [baseUrl]   (needs playwright and @axe-core/playwright in node_modules)
// baseUrl: a static server over a build made without NEXT_PUBLIC_SPET_API. It clicks "Split" and "Test", so never
// point it at a server whose API reaches a paid model.
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const base = process.argv[2] ?? "http://localhost:3101";
const browser = await chromium.launch({ headless: true });
let fail = 0;
let minor = 0;

const split = (p) => p.getByRole("button", { name: "Split into parts" }).click();
const pages = [
  ["/ start", "/", null],
  ["/ changed prompt", "/", (p) => p.locator("textarea#prompt").fill("You are a pirate.\n\nAnswer in rhymes.")],
  ["/ parts", "/", async (p) => { await split(p); await p.getByRole("button", { name: "See the questions" }).click(); }],
  ["/ parts merged, no model", "/", async (p) => { await split(p); await p.locator("button[role=switch]").nth(1).click(); }],
  ["/ running", "/", async (p) => { await split(p); await p.getByRole("button", { name: /^Test/ }).click(); await p.waitForTimeout(1600); }],
  ["/ result", "/", async (p) => { await split(p); await p.getByRole("button", { name: /^Test/ }).click(); await p.waitForSelector(".row.result", { timeout: 15000 }); }],
  ["/#part=4 open + more detail", "/#part=4", (p) => p.getByRole("button", { name: "More detail" }).click()],
  ["/#part=3 no change", "/#part=3", (p) => p.getByRole("button", { name: "More detail" }).click()],
  ["/#part=7 untestable", "/#part=7", (p) => p.getByRole("button", { name: "More detail" }).click()],
  ["saved run", "/runs/lumen-original-probes/", null],
  ["stub-demo", "/run/?id=stub-demo#part=6", null],
  ["runs", "/runs/", null],
  ["method", "/method/", null],
];

for (const width of [1440, 390]) {
  for (const [label, path, act] of pages) {
    const page = await (await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 } })).newPage();
    await page.goto(base + path, { waitUntil: "networkidle" });
    if (/run/.test(path) || path.includes("#")) await page.waitForSelector(".row.result").catch(() => {});
    if (act) await act(page);
    await page.waitForTimeout(700);
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    const bad = r.violations.filter((v) => ["serious", "critical"].includes(v.impact));
    console.log(`axe ${width} ${label.padEnd(30)} ${bad.length} serious/critical, ${r.violations.length - bad.length} minor`);
    for (const v of r.violations) console.log(`   - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}) e.g. ${v.nodes[0]?.target}`);
    fail += bad.length;
    minor += r.violations.length - bad.length;
    await page.close();
  }
}

// Reduced motion: opening a part, its notes and "More detail" must change at once (nothing mid-transition)
{
  const page = await (await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 900 } })).newPage();
  // an element is mid-transition if its transform, opacity or height still differs a second later
  const styles = () => page.evaluate(() => [...document.querySelectorAll("main *")].map((el) => {
    const s = getComputedStyle(el);
    return `${s.transform}|${s.opacity}|${Math.round(el.getBoundingClientRect().height)}`;
  }));
  const moving = async () => {
    const a = await styles();
    await page.waitForTimeout(1000);
    const b = await styles();
    return a.filter((x, i) => b.length === a.length && x !== b[i]);
  };
  await page.goto(base + "/run/?id=lumen-original-probes", { waitUntil: "networkidle" });
  await page.waitForSelector(".row.result");
  await page.waitForTimeout(40);
  const a = await moving();
  await page.locator("#part-4 .text-btn").click();
  await page.waitForTimeout(40);
  const b = await moving();
  const h = await page.locator("#detail-4").evaluate((el) => el.getBoundingClientRect().height);
  await page.getByRole("button", { name: "More detail" }).click();
  await page.waitForTimeout(40);
  const c = await moving();
  console.log(`reduced motion: mid-transition 40ms after notes load: ${a.length}, after opening a part: ${b.length} (detail height ${Math.round(h)}px), after More detail: ${c.length}`);
  if (a.length || b.length || c.length || h < 100) { fail++; console.log("   ", a, b, c); }
  await page.close();
}

await browser.close();
console.log(`total: ${fail} serious/critical, ${minor} minor`);
process.exit(fail ? 1 : 0);
