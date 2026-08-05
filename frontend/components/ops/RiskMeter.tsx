export function RiskMeter({
  label,
  currentLabel,
  limitLabel,
  pct,
}: {
  label: string;
  currentLabel: string;
  limitLabel: string;
  pct: number | null;
}) {
  const clamped = pct == null || !Number.isFinite(pct) ? null : Math.max(0, Math.min(100, pct));
  const tone =
    clamped == null
      ? "bg-muted"
      : clamped >= 85
        ? "bg-negative"
        : clamped >= 60
          ? "bg-warning"
          : "bg-positive";

  return (
    <article className="rounded-card border border-border bg-surface-raised/40 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold text-foreground">{label}</p>
        <p className="text-[12px] tabular text-secondary">
          {currentLabel} / {limitLabel}
        </p>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-surface-hover"
        role="meter"
        aria-label={`${label} usage`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped ?? undefined}
        aria-valuetext={clamped == null ? "Unavailable" : `${clamped.toFixed(0)} percent`}
      >
        {clamped != null ? (
          <div className={`h-full rounded-full ${tone}`} style={{ width: `${clamped}%` }} />
        ) : (
          <div className="h-full w-0" />
        )}
      </div>
      <p className="mt-2 text-[12px] text-muted">
        {clamped == null ? "Usage unavailable from API" : `${clamped.toFixed(1)}% used`}
      </p>
    </article>
  );
}
