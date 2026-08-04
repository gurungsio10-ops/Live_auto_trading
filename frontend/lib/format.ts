const LOCALE = "en-US";

function toNumber(value: string | number): number {
  return typeof value === "string" ? Number(value) : value;
}

export function formatMoney(
  value: string | number,
  digits = 2,
  currency: "USD" | "GBP" = "USD",
): string {
  const n = toNumber(value);
  if (!Number.isFinite(n)) return "—";
  try {
    return new Intl.NumberFormat(LOCALE, {
      style: "currency",
      currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(n);
  } catch {
    const symbol = currency === "GBP" ? "£" : "$";
    const sign = n < 0 ? "-" : "";
    return `${sign}${symbol}${Math.abs(n).toLocaleString(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })}`;
  }
}

/** Compact money for tight mobile cards ($1.25K / $1.20M). */
export function formatCompactMoney(
  value: string | number,
  currency: "USD" | "GBP" = "USD",
): string {
  const n = toNumber(value);
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs < 1000) return formatMoney(n, 2, currency);
  try {
    return new Intl.NumberFormat(LOCALE, {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    const symbol = currency === "GBP" ? "£" : "$";
    const sign = n < 0 ? "-" : "";
    if (abs >= 1_000_000_000) return `${sign}${symbol}${(abs / 1_000_000_000).toFixed(2)}B`;
    if (abs >= 1_000_000) return `${sign}${symbol}${(abs / 1_000_000).toFixed(2)}M`;
    return `${sign}${symbol}${(abs / 1_000).toFixed(2)}K`;
  }
}

export function formatPrice(value: string | number, digits = 2): string {
  return formatMoney(value, digits, "USD");
}

export function formatPct(value: string | number, digits = 2): string {
  const n = toNumber(value);
  if (!Number.isFinite(n)) return "—";
  // Treat fractional ratios in (-1, 1) excluding 0 as fractions; keep 0 as 0.00%.
  const pct = n !== 0 && Math.abs(n) < 1 ? n * 100 : n;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

export function formatQty(value: string | number, digits = 6): string {
  const n = toNumber(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function formatQtyAsset(
  value: string | number,
  asset = "BTC",
  digits = 6,
): string {
  const q = formatQty(value, digits);
  return q === "—" ? q : `${q} ${asset}`;
}

export function formatTs(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

/** Shorter timestamp for mobile cards. */
export function formatTsShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(5, 16).replace("T", " ");
}

export function pnlTone(value: string | number): "gain" | "loss" | "flat" {
  const n = toNumber(value);
  if (!Number.isFinite(n) || n === 0) return "flat";
  return n > 0 ? "gain" : "loss";
}

/** Pick compact vs full money based on viewport hint / magnitude. */
export function formatMoneyResponsive(
  value: string | number,
  opts?: { compact?: boolean; currency?: "USD" | "GBP" },
): { display: string; full: string } {
  const currency = opts?.currency ?? "USD";
  const full = formatMoney(value, 2, currency);
  const display = opts?.compact ? formatCompactMoney(value, currency) : full;
  return { display, full };
}
