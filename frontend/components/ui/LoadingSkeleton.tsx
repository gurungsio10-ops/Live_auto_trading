export function LoadingSkeleton({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className}`} aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-16 animate-pulse rounded-card border border-border bg-surface-raised/70"
        />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="rounded-card border border-border bg-surface px-4 py-6">
      <div className="mb-3 h-4 w-40 animate-pulse rounded bg-surface-hover" />
      <LoadingSkeleton rows={2} />
      <p className="mt-3 text-[13px] text-muted">{label}</p>
    </div>
  );
}
