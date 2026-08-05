export function DemoBanner({
  demo,
  backendError,
}: {
  demo?: boolean;
  backendError?: string;
}) {
  if (!demo && !backendError) return null;
  return (
    <div
      className="rounded-card border border-warning/35 bg-warning-soft px-4 py-3 text-[13px] text-foreground"
      role="status"
    >
      <p className="font-semibold">{demo ? "Demo data" : "Backend unavailable"}</p>
      <p className="mt-1 text-secondary">
        {backendError
          ? `Project Atlas could not use live backend data. ${backendError}`
          : "Showing demo data because the backend is unavailable."}
      </p>
    </div>
  );
}
