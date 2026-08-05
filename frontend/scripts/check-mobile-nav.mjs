/**
 * Static mobile IA contract tests (no browser).
 * Ensures Home/Trade/Positions/Activity/More remain the bottom-nav set
 * and that no "Go Live" label sneaks into primary nav.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { BOTTOM_NAV, DESKTOP_NAV, MORE_LINKS, navActive } from "../lib/nav";

const widths = [320, 375, 390, 430, 768, 1024, 1440];

assert.deepEqual(
  BOTTOM_NAV.map((i) => i.label),
  ["Home", "Trade", "Positions", "Activity", "More"],
);

assert.equal(BOTTOM_NAV.length, 5);
assert.ok(navActive("/", "/"));
assert.ok(navActive("/orders", "/orders"));
assert.ok(navActive("/positions/x", "/positions"));
assert.equal(navActive("/orders", "/"), false);

const allLabels = [...BOTTOM_NAV, ...DESKTOP_NAV, ...MORE_LINKS]
  .map((i) => i.label.toLowerCase())
  .join(" ");
assert.equal(allLabels.includes("go live"), false);
assert.equal(allLabels.includes("live trading"), false);

const morePage = readFileSync(join(__dirname, "../app/more/page.tsx"), "utf8");
assert.ok(morePage.includes("Developed by Saugat Gurung"));
assert.ok(morePage.includes("No “Go Live”") || morePage.includes('No "Go Live"'));

const shell = readFileSync(
  join(__dirname, "../components/layout/MobileBottomNav.tsx"),
  "utf8",
);
assert.ok(shell.includes("min-h-[44px]"));
assert.ok(shell.includes("lg:hidden"));

const sidebar = readFileSync(
  join(__dirname, "../components/layout/Sidebar.tsx"),
  "utf8",
);
assert.ok(sidebar.includes("lg:flex"));
assert.ok(sidebar.includes("hidden"));

// Document required audit widths for MOBILE_UI_AUDIT.md consumers.
assert.deepEqual(widths, [320, 375, 390, 430, 768, 1024, 1440]);

console.log("mobile_nav_contract_ok", {
  bottom: BOTTOM_NAV.map((i) => i.href),
  widths,
});
