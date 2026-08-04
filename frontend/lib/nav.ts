export type NavItem = {
  href: string;
  label: string;
  /** Short label for bottom nav */
  shortLabel?: string;
  icon: "overview" | "trading" | "portfolio" | "activity" | "more" | "signals" | "risk" | "strategies" | "backtests" | "settings";
  /** Show in desktop sidebar primary list */
  desktop?: boolean;
  /** Show in mobile bottom bar */
  mobilePrimary?: boolean;
  /** Show in mobile "More" drawer */
  mobileMore?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview", shortLabel: "Home", icon: "overview", desktop: true, mobilePrimary: true },
  { href: "/orders", label: "Trading", shortLabel: "Trade", icon: "trading", desktop: true, mobilePrimary: true },
  { href: "/positions", label: "Portfolio", shortLabel: "Portfolio", icon: "portfolio", desktop: true, mobilePrimary: true },
  { href: "/signals", label: "Activity", shortLabel: "Activity", icon: "activity", desktop: true, mobilePrimary: true },
  { href: "/risk-events", label: "Risk events", icon: "risk", desktop: true, mobileMore: true },
  { href: "/strategies", label: "Strategies", icon: "strategies", desktop: true, mobileMore: true },
  { href: "/backtests", label: "Backtests", icon: "backtests", desktop: true, mobileMore: true },
  { href: "/settings", label: "Settings", icon: "settings", desktop: true, mobileMore: true },
];

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
