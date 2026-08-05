import Link from "next/link";
import { Badge } from "@/components/ui/Badge";

export type StatusTone = "positive" | "negative" | "warning" | "neutral" | "info";

export type SystemStatusItem = {
  key: string;
  label: string;
  value: string;
  tone: StatusTone;
};

export function SystemStatusCard({
  items,
  viewAllHref = "/system-health",
}: {
  items: SystemStatusItem[];
  viewAllHref?: string;
}) {
  return (
    <section className="rounded-card border border-border bg-surface p-4 shadow-soft">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold text-foreground">System status</h2>
        <Link
          href={viewAllHref}
          className="min-h-touch text-[13px] font-semibold text-brand hover:underline"
        >
          View all
        </Link>
      </div>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {items.map((item) => (
          <li
            key={item.key}
            className="rounded-control border border-border bg-surface-raised/40 px-3 py-2.5"
          >
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{item.label}</p>
            <div className="mt-1.5">
              <Badge tone={item.tone}>{item.value}</Badge>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
