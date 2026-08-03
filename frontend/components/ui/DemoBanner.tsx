export function DemoBanner({
  demo,
  backendError,
}: {
  demo?: boolean;
  backendError?: string;
}) {
  if (!demo && !backendError) return null;
  return (
    <div className="mb-4 border border-terminal-warn/40 bg-terminal-warn/10 px-3 py-2 text-[11px] text-terminal-warn font-mono">
      {demo
        ? "Demo data — FastAPI backend unavailable or endpoint missing. UI remains fully interactive via local mock state."
        : null}
      {backendError ? ` ${backendError}` : null}
    </div>
  );
}
