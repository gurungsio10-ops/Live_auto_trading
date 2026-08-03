export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[160px] items-center justify-center border border-dashed border-terminal-border bg-terminal-panel/50">
      <div className="flex items-center gap-3 text-xs text-terminal-dim font-mono">
        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-terminal-accent" />
        {label}
      </div>
    </div>
  );
}
