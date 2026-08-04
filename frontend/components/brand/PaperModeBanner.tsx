import { Badge } from "@/components/ui/Badge";
import { BRAND } from "@/lib/brand";

export function PaperModeBanner({ className = "" }: { className?: string }) {
  return (
    <div
      className={[
        "flex flex-wrap items-center gap-2 border border-terminal-warn/40 bg-terminal-warn/10 px-3 py-2",
        className,
      ].join(" ")}
      role="status"
      aria-live="polite"
    >
      <Badge tone="warn">{BRAND.paperBadge}</Badge>
      <p className="min-w-0 text-[11px] leading-snug text-terminal-dim">
        {BRAND.paperDisclaimer}
      </p>
    </div>
  );
}
