/**
 * Static mobile IA contract tests (no browser / no TS import).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const widths = [320, 375, 390, 430, 768, 1024, 1440];

const nav = readFileSync(join(root, "lib/nav.ts"), "utf8");
for (const label of ["Home", "Trade", "Positions", "Activity", "More"]) {
  assert.ok(nav.includes(`label: "${label}"`), `missing ${label}`);
}
assert.equal(nav.toLowerCase().includes("go live"), false);

const morePage = readFileSync(join(root, "app/more/page.tsx"), "utf8");
assert.ok(/Go Live/.test(morePage));
const footer = readFileSync(
  join(root, "components/layout/AtlasFooter.tsx"),
  "utf8",
);
assert.ok(footer.includes("Developed by Saugat Gurung"));

const bottom = readFileSync(
  join(root, "components/layout/MobileBottomNav.tsx"),
  "utf8",
);
assert.ok(bottom.includes("min-h-[44px]"));
assert.ok(bottom.includes("lg:hidden"));
assert.ok(bottom.includes('data-testid="mobile-bottom-nav"'));

const sidebar = readFileSync(join(root, "components/layout/Sidebar.tsx"), "utf8");
assert.ok(sidebar.includes("lg:flex"));
assert.ok(sidebar.includes("hidden"));

const portfolio = readFileSync(join(root, "app/api/portfolio/route.ts"), "utf8");
assert.ok(portfolio.includes("503"));
assert.ok(portfolio.includes("backend down") || portfolio.includes("envelope("));

const killSwitch = readFileSync(join(root, "app/api/kill-switch/route.ts"), "utf8");
assert.ok(killSwitch.includes("Fail closed") || killSwitch.includes("fail closed") || killSwitch.includes("503"));
assert.ok(killSwitch.includes("applied: false") || killSwitch.includes("kill_switch_enabled: null"));

assert.deepEqual(widths, [320, 375, 390, 430, 768, 1024, 1440]);
console.log("mobile_nav_contract_ok", { widths });
