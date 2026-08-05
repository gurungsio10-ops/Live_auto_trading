import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bot,
  Briefcase,
  Cable,
  CandlestickChart,
  ClipboardList,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
  MoreHorizontal,
  Receipt,
  Settings,
  ShieldAlert,
  Sparkles,
  Timer,
  WalletCards,
} from "lucide-react";

export type NavKey =
  | "overview"
  | "markets"
  | "ai"
  | "portfolio"
  | "orders"
  | "activity"
  | "strategies"
  | "backtests"
  | "paperTrading"
  | "scheduler"
  | "systemHealth"
  | "audit"
  | "risk"
  | "connection"
  | "settings"
  | "about";

export type NavItem = {
  key: NavKey;
  href: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
  desktop: boolean;
  mobilePrimary?: boolean;
  mobileMore?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", href: "/", label: "Overview", shortLabel: "Home", icon: LayoutDashboard, desktop: true, mobilePrimary: true },
  { key: "markets", href: "/markets", label: "Markets", shortLabel: "Markets", icon: CandlestickChart, desktop: true, mobilePrimary: true },
  { key: "ai", href: "/ai-decisions", label: "AI Decisions", shortLabel: "AI", icon: Bot, desktop: true, mobilePrimary: true },
  { key: "portfolio", href: "/portfolio", label: "Portfolio", shortLabel: "Portfolio", icon: Briefcase, desktop: true, mobilePrimary: true },
  { key: "orders", href: "/orders", label: "Orders", icon: Receipt, desktop: true, mobileMore: true },
  { key: "activity", href: "/activity", label: "Activity", icon: Activity, desktop: true, mobileMore: true },
  { key: "strategies", href: "/strategies", label: "Strategies", icon: Sparkles, desktop: true, mobileMore: true },
  { key: "backtests", href: "/backtests", label: "Backtests", icon: FlaskConical, desktop: true, mobileMore: true },
  { key: "paperTrading", href: "/paper-trading", label: "Paper trading", icon: WalletCards, desktop: true, mobileMore: true },
  { key: "scheduler", href: "/scheduler", label: "Scheduler", icon: Timer, desktop: true, mobileMore: true },
  { key: "systemHealth", href: "/system-health", label: "System health", icon: HeartPulse, desktop: true, mobileMore: true },
  { key: "audit", href: "/audit", label: "Audit journal", icon: ClipboardList, desktop: true, mobileMore: true },
  { key: "risk", href: "/risk", label: "Risk Centre", icon: ShieldAlert, desktop: true, mobileMore: true },
  { key: "connection", href: "/connection", label: "Connection", icon: Cable, desktop: true, mobileMore: true },
  { key: "settings", href: "/settings", label: "Settings", icon: Settings, desktop: true, mobileMore: true },
  { key: "about", href: "/about", label: "About", icon: BarChart3, desktop: false, mobileMore: true },
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
