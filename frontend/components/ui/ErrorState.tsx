import { Button } from "./Button";

export function ErrorState({
  title = "Failed to load",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex min-h-[160px] flex-col items-center justify-center gap-3 border border-terminal-loss/40 bg-terminal-loss/5 px-6 text-center">
      <p className="font-display text-sm uppercase tracking-[0.12em] text-terminal-loss">
        {title}
      </p>
      {message && <p className="max-w-lg text-xs text-terminal-dim font-mono">{message}</p>}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} type="button">
          Retry
        </Button>
      )}
    </div>
  );
}
