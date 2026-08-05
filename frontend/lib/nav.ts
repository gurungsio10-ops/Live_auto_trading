import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BookOpen,
  Briefcase,
  ClipboardList,
  FlaskConical,
  HeartPulse,
  HelpCircle,
  LayoutDashboard,
  MoreHorizontal,
  Power,
  Receipt,
  Settings,
  ShieldAlert,
  Sparkles,
  Timer,
  Radio,
} from "lucide-react";

export type NavKey =
  | "overview"
  | "positions"
  | "orders"
  | "signals"
  | "more"
  | "strategies"
  | "backtests"
  | "risk"
  | "riskEvents"
  | "journal"
  | "scheduler"
  | "systemHealth"
  | "settings"
  | "help"
  | "about"
  | "killSwitch"
  | "markets"
  | "portfolio"
  | "ai"
  | "activity"
  | "paperTrading"
  | "connection"
  | "audit";

export type NavItem = {
  key: NavKey;
  href: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
  desktop: boolean;
  mobilePrimary?: boolean;
  mobileMore?: boolean;
  drawerMain?: boolean;
  drawerSystem?: boolean;
  drawerAccount?: boolean;
  moreTrading?: boolean;
  moreSystem?: boolean;
  moreInfo?: boolean;
};

/** Primary mobile bottom nav: Overview, Positions, Orders, Signals (+ More button). */
export const NAV_ITEMS: NavItem[] = [
  {
    key: "overview",
    href: "/",
    label: "Overview",
    shortLabel: "Overview",
    icon: LayoutDashboard,
    desktop: true,
    mobilePrimary: true,
    drawerMain: true,
  },
  {
    key: "positions",
    href: "/positions",
    label: "Positions",
    shortLabel: "Positions",
    icon: Briefcase,
    desktop: true,
    mobilePrimary: true,
    drawerMain: true,
  },
  {
    key: "orders",
    href: "/orders",
    label: "Orders",
    shortLabel: "Orders",
    icon: Receipt,
    desktop: true,
    mobilePrimary: true,
    drawerMain: true,
  },
  {
    key: "signals",
    href: "/signals",
    label: "Signals",
    shortLabel: "Signals",
    icon: Radio,
    desktop: true,
    mobilePrimary: true,
    drawerMain: true,
  },
  {
    key: "more",
    href: "/more",
    label: "More",
    shortLabel: "More",
    icon: MoreHorizontal,
    desktop: false,
    mobilePrimary: false,
  },
  {
    key: "strategies",
    href: "/strategies",
    label: "Strategies",
    icon: Sparkles,
    desktop: true,
    mobileMore: true,
    drawerMain: true,
    moreTrading: true,
  },
  {
    key: "backtests",
    href: "/backtests",
    label: "Backtests",
    icon: FlaskConical,
    desktop: true,
    mobileMore: true,
    drawerMain: true,
    moreTrading: true,
  },
  {
    key: "riskEvents",
    href: "/risk-events",
    label: "Risk Events",
    icon: Activity,
    desktop: true,
    mobileMore: true,
    drawerMain: true,
    moreTrading: true,
  },
  {
    key: "journal",
    href: "/journal",
    label: "Journal",
    icon: BookOpen,
    desktop: true,
    mobileMore: true,
    drawerMain: true,
    moreTrading: true,
  },
  {
    key: "risk",
    href: "/risk",
    label: "Risk Centre",
    icon: ShieldAlert,
    desktop: true,
    mobileMore: true,
    moreTrading: true,
  },
  {
    key: "killSwitch",
    href: "/kill-switch",
    label: "Kill Switch",
    icon: Power,
    desktop: true,
    mobileMore: true,
    moreSystem: true,
  },
  {
    key: "scheduler",
    href: "/scheduler",
    label: "Scheduler",
    icon: Timer,
    desktop: true,
    mobileMore: true,
    drawerSystem: true,
    moreSystem: true,
  },
  {
    key: "systemHealth",
    href: "/system-health",
    label: "System Health",
    icon: HeartPulse,
    desktop: true,
    mobileMore: true,
    drawerSystem: true,
    moreSystem: true,
  },
  {
    key: "settings",
    href: "/settings",
    label: "Settings",
    icon: Settings,
    desktop: true,
    mobileMore: true,
    drawerSystem: true,
    moreSystem: true,
  },
  {
    key: "help",
    href: "/help",
    label: "Help and Docs",
    icon: HelpCircle,
    desktop: false,
    mobileMore: true,
    moreInfo: true,
  },
  {
    key: "about",
    href: "/about",
    label: "About Atlas",
    icon: ClipboardList,
    desktop: false,
    mobileMore: true,
    moreInfo: true,
  },
  // Legacy routes kept accessible via desktop/more redirects
  {
    key: "portfolio",
    href: "/portfolio",
    label: "Portfolio",
    icon: Briefcase,
    desktop: false,
  },
  {
    key: "ai",
    href: "/ai-decisions",
    label: "AI Decisions",
    icon: Radio,
    desktop: false,
  },
  {
    key: "audit",
    href: "/audit",
    label: "Audit journal",
    icon: ClipboardList,
    desktop: false,
  },
  {
    key: "markets",
    href: "/markets",
    label: "Markets",
    icon: Activity,
    desktop: true,
    mobileMore: true,
  },
  {
    key: "connection",
    href: "/connection",
    label: "Connection",
    icon: HeartPulse,
    desktop: true,
    mobileMore: true,
  },
  {
    key: "activity",
    href: "/activity",
    label: "Activity",
    icon: Activity,
    desktop: true,
    mobileMore: true,
  },
  {
    key: "paperTrading",
    href: "/paper-trading",
    label: "Paper trading",
    icon: Briefcase,
    desktop: true,
    mobileMore: true,
  },
];

export const MOBILE_MORE_ICON = MoreHorizontal;

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href.includes("#")) {
    const base = href.split("#")[0];
    return pathname === base || pathname.startsWith(`${base}/`);
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Derive a restrained 0–100 risk score from existing portfolio/risk fields (not a backend prediction). */
export function deriveRiskScore(input: {
  kill_switch_enabled?: boolean;
  trading_paused?: boolean;
  drawdown?: string | number;
  maxDrawdown?: string | number;
  daily_pnl?: string | number;
  maxDailyLoss?: string | number;
  equity?: string | number;
}): { score: number; label: string; source: "derived" } {
  if (input.kill_switch_enabled) {
    return { score: 100, label: "Blocked", source: "derived" };
  }
  let score = 0;
  if (input.trading_paused) score += 25;
  const dd = Math.abs(Number(input.drawdown ?? 0));
  const maxDd = Math.abs(Number(input.maxDrawdown ?? 0));
  const ddPct = dd <= 1 ? dd * 100 : dd;
  const maxDdPct = maxDd <= 1 && maxDd !== 0 ? maxDd * 100 : maxDd;
  if (maxDdPct > 0) {
    score += Math.min(50, (ddPct / maxDdPct) * 50);
  }
  const equity = Math.abs(Number(input.equity ?? 0));
  const daily = Number(input.daily_pnl ?? 0);
  const maxLoss = Math.abs(Number(input.maxDailyLoss ?? 0));
  const maxLossAmt = maxLoss <= 1 && equity > 0 ? equity * maxLoss : maxLoss;
  if (maxLossAmt > 0 && daily < 0) {
    score += Math.min(25, (Math.abs(daily) / maxLossAmt) * 25);
  }
  score = Math.max(0, Math.min(100, Math.round(score)));
  const label =
    score >= 80 ? "Elevated risk" : score >= 40 ? "Moderate risk" : "Very low risk";
  return { score, label, source: "derived" };
}
