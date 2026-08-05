export type DisplayCurrency = "USD" | "GBP";

const LOCALE = "en-GB";

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isFinite(n) ? n : null;
}

export function formatMoney(
  value: string | number | null | undefined,
  currency: DisplayCurrency = "USD",
  digits = 2,
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function formatCompactMoney(
  value: string | number | null | undefined,
  currency: DisplayCurrency = "USD",
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  if (Math.abs(n) < 1000) return formatMoney(n, currency);
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatPrice(
  value: string | number | null | undefined,
  currency: DisplayCurrency = "USD",
): string {
  return formatMoney(value, currency, 2);
}

export function formatPct(
  value: string | number | null | undefined,
  digits = 2,
  signed = false,
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  const pct = n !== 0 && Math.abs(n) < 1 ? n * 100 : n;
  const prefix = signed && pct > 0 ? "+" : "";
  return `${prefix}${pct.toFixed(digits)}%`;
}

export function formatQty(value: string | number | null | undefined, digits = 6): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return n.toLocaleString(LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function formatQtyAsset(
  value: string | number | null | undefined,
  asset = "BTC",
  digits = 6,
): string {
  const q = formatQty(value, digits);
  return q === "—" ? q : `${q} ${asset}`;
}

export function formatSignedPnl(
  value: string | number | null | undefined,
  currency: DisplayCurrency = "USD",
): string {
  const n = toNumber(value);
  if (n === null) return "—";
  const abs = formatMoney(Math.abs(n), currency);
  if (n > 0) return `+${abs}`;
  if (n < 0) return `−${abs.replace("-", "")}`;
  return abs;
}

export function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

export function formatTsShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(5, 16).replace("T", " ");
}

export function formatRelativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const delta = Math.max(0, Math.floor((now - d.getTime()) / 1000));
  if (delta < 5) return "just now";
  if (delta < 60) return `${delta} seconds ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)} minutes ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} hours ago`;
  return `${Math.floor(delta / 86400)} days ago`;
}

export function pnlTone(value: string | number | null | undefined): "gain" | "loss" | "flat" {
  const n = toNumber(value);
  if (n === null || n === 0) return "flat";
  return n > 0 ? "gain" : "loss";
}

/** @deprecated use formatSignedPnl / formatMoney */
export function formatMoneyResponsive(
  value: string | number,
  opts?: { compact?: boolean; currency?: DisplayCurrency },
): { display: string; full: string } {
  const currency = opts?.currency ?? "USD";
  const full = formatMoney(value, currency);
  const display = opts?.compact ? formatCompactMoney(value, currency) : full;
  return { display, full };
}
