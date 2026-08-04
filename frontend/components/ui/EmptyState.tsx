export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded-card border border-dashed border-border bg-surface-raised/40 px-4 py-8 text-center">
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-secondary">
          {description}
        </p>
      ) : null}
    </div>
  );
}
