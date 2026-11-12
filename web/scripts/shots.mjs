// Screenshot the static export. Usage: node scripts/shots.mjs <outDir> [baseUrl]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const out = process.argv[2] ?? "shots";
const base = process.argv[3] ?? "http://localhost:3101";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const errors = [];

async function shoot(name, url, { width = 1440, height = 1000, scheme = "light", act, full = true } = {}) {
  const page = await browser.newPage({ viewport: { width, height }, colorScheme: scheme, deviceScaleFactor: 1 });
  page.on("console", (m) => m.type() === "error" && errors.push(`${name}: ${m.text()}`));
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message}`));
  await page.goto(base + url, { waitUntil: "networkidle" });
  if (act) await act(page);
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: full });
  await page.close();
}

const removeSection = (label) => async (p) => {
  await p.getByRole("button", { name: `Remove section: ${label}` }).click();
};

await shoot("home", "/");
await shoot("home-removed", "/", { act: removeSection("Apology policy"), full: false });
await shoot("run", "/runs/stub-demo/");
await shoot("run-dark-removed", "/runs/stub-demo/", { scheme: "dark", act: removeSection("Formatting"), full: false });
await shoot("method", "/method/");
await shoot("mobile", "/", { width: 390, height: 844 });
await browser.close();
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console errors");
