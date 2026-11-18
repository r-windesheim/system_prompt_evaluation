// Screenshots of the five states. Run from web/: node ../docs/prototypes/minimal/shoot.mjs
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.resolve(here, "../../../web/package.json"));
const { chromium } = require("playwright");
const base = pathToFileURL(path.join(here, "index.html")).href;
const browser = await chromium.launch({ headless: true });
const errors = [];

async function shot(name, { width = 1440, height = 900, query = "?fast" } = {}, act) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on("console", (m) => m.type() === "error" && errors.push(`${name}: ${m.text()}`));
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message}`));
  await page.goto(base + query, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  if (act) await act(page);
  await page.mouse.move(0, 0);
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(here, `${name}.png`) });
  await ctx.close();
}

const split = (p) => p.click("#split");
const toResult = async (p) => { await split(p); await p.click("#test"); await p.waitForSelector('body[data-state="result"]'); };
const openPart = (i) => async (p) => {
  await toResult(p);
  await p.click(`.part[data-part="${i}"] .para`);
  await p.evaluate((i) => {
    const el = document.querySelector(`.part[data-part="${i}"]`);
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 28);
  }, i);
};

await shot("state1");
await shot("state2", {}, split);
await shot("state3", { query: "?hold=3" }, async (p) => { await split(p); await p.click("#test"); await p.waitForSelector('body[data-testing="3"]'); });
await shot("state4", {}, toResult);
await shot("state5", {}, openPart(3));
await shot("state4-mobile", { width: 390, height: 844 }, toResult);
await shot("state5-mobile", { width: 390, height: 844 }, openPart(3));

if (process.argv[2] === "check") {
  const out = process.argv[3];
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(base + "?fast"); await p.evaluate(() => document.fonts.ready);
  await split(p); await p.click('button.gap[data-i="4"]'); await p.hover('button.gap[data-i="1"]');
  await p.screenshot({ path: path.join(out, "merged.png") });
  await p.click("#test").catch(() => {}); await p.mouse.move(0, 0);
  await p.screenshot({ path: path.join(out, "merged-after-test.png") });
  await p.click('button.gap[data-i="4"]'); await p.click("#test"); await p.waitForSelector('body[data-state="result"]');
  await p.click('.part[data-part="0"] .para'); await p.click(".more"); await p.waitForTimeout(600);
  await p.screenshot({ path: path.join(out, "deep0.png"), fullPage: true });
  await p.click('.part[data-part="6"] .para'); await p.click(".more"); await p.waitForTimeout(600);
  await p.screenshot({ path: path.join(out, "deep6.png"), fullPage: true });
  await ctx.close();
}
await browser.close();
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console errors");
