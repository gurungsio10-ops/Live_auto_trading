/**
 * Canonical Atlas navigation IA.
 * Mobile uses BOTTOM_NAV; desktop sidebar uses DESKTOP_NAV + MORE_LINKS.
 */

export type NavItem = {
  href: string;
  label: string;
  /** Short label for bottom nav (≤6 chars preferred). */
  short?: string;
};

/** Fixed bottom navigation — required mobile IA. */
export const BOTTOM_NAV: readonly NavItem[] = [
  { href: "/", label: "Home", short: "Home" },
  { href: "/orders", label: "Trade", short: "Trade" },
  { href: "/positions", label: "Positions", short: "Pos" },
  { href: "/activity", label: "Activity", short: "Activity" },
  { href: "/more", label: "More", short: "More" },
] as const;

/** Full desktop sidebar order. */
export const DESKTOP_NAV: readonly NavItem[] = [
  { href: "/", label: "Home" },
  { href: "/orders", label: "Trade" },
  { href: "/positions", label: "Positions" },
  { href: "/activity", label: "Activity" },
  { href: "/recovery", label: "Recovery" },
  { href: "/fills", label: "Fills" },
  { href: "/signals", label: "Signals" },
  { href: "/risk-events", label: "Risk" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/settings", label: "Settings" },
  { href: "/more", label: "More / About" },
] as const;

/** Secondary destinations surfaced from More. */
export const MORE_LINKS: readonly NavItem[] = [
  { href: "/recovery", label: "Recovery" },
  { href: "/fills", label: "Fills" },
  { href: "/signals", label: "Signals" },
  { href: "/risk-events", label: "Risk events" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtests", label: "Backtests" },
  { href: "/settings", label: "Settings" },
] as const;

export function navActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
