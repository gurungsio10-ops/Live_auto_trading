/**
 * Capture Atlas dashboard viewports for MOBILE_UI_AUDIT evidence.
 */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WIDTHS = [320, 375, 390, 430, 768, 1024, 1440];
const OUT = path.join(__dirname, "../../artifacts/mobile-viewports");
const BASE = process.env.ATLAS_UI_URL || "http://127.0.0.1:3000";
const USER = process.env.ATLAS_DASHBOARD_USER || "admin";
const PASS = process.env.ATLAS_DASHBOARD_PASSWORD || "atlas";

async function login(context) {
  // Prefer API login so controlled React inputs cannot block automation.
  const res = await context.request.post(`${BASE}/api/auth/login`, {
    data: { username: USER, password: PASS, remember: true },
  });
  if (!res.ok()) {
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || "/usr/local/bin/google-chrome",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const results = [];

  for (const width of WIDTHS) {
    const context = await browser.newContext({
      viewport: { width, height: Math.max(844, Math.round(width * 1.8)) },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await login(context);
    await page.goto(`${BASE}/`, { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForSelector('[data-testid="home-overview"]', {
      state: "attached",
      timeout: 30000,
    });
    await page.waitForTimeout(600);

    const bottomVisible = await page
      .locator('[data-testid="mobile-bottom-nav"]')
      .evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display !== "none" && style.visibility !== "hidden";
      })
      .catch(() => false);
    const sidebarVisible = await page
      .locator('[data-testid="desktop-sidebar"]')
      .evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display !== "none" && style.visibility !== "hidden";
      })
      .catch(() => false);
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return {
        scrollWidth: doc.scrollWidth,
        clientWidth: doc.clientWidth,
        overflowX: doc.scrollWidth > doc.clientWidth + 1,
      };
    });
    const file = path.join(OUT, `home-${width}.png`);
    await page.screenshot({ path: file, fullPage: true });
    results.push({
      width,
      bottomNavVisible: bottomVisible,
      sidebarVisible,
      overflowX: overflow.overflowX,
      scrollWidth: overflow.scrollWidth,
      clientWidth: overflow.clientWidth,
      screenshot: file,
    });
    await context.close();
  }

  await browser.close();
  const report = path.join(OUT, "viewport-results.json");
  fs.writeFileSync(report, JSON.stringify(results, null, 2));
  console.log(JSON.stringify({ ok: true, results }, null, 2));
  const bad = results.filter(
    (r) =>
      r.overflowX ||
      (r.width < 1024 && !r.bottomNavVisible) ||
      (r.width >= 1024 && !r.sidebarVisible),
  );
  if (bad.length) {
    console.error("viewport_failures", bad);
    process.exit(2);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
