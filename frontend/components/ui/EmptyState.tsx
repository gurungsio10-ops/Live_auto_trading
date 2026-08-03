export function EmptyState({
  title = "No data",
  description = "Nothing to display for the current filters.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex min-h-[160px] flex-col items-center justify-center gap-2 border border-dashed border-terminal-border bg-terminal-panel/40 px-6 text-center">
      <p className="font-display text-sm uppercase tracking-[0.12em] text-terminal-text">
        {title}
      </p>
      <p className="max-w-md text-xs text-terminal-dim">{description}</p>
    </div>
  );
}
