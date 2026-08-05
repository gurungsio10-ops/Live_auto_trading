import { Button } from "./Button";

export function ErrorState({
  title = "Unable to load data",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="rounded-card border border-negative/30 bg-negative-soft px-4 py-5"
      role="alert"
    >
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-secondary">{message}</p>
      {onRetry ? (
        <Button type="button" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
