import { BRAND } from "@/lib/brand";
import { Badge } from "@/components/ui/Badge";

export function BrandMark({
  showSubtitle = true,
  showPaperBadge = false,
  size = "md",
}: {
  showSubtitle?: boolean;
  showPaperBadge?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const titleClass =
    size === "lg"
      ? "text-3xl tracking-[0.16em]"
      : size === "sm"
        ? "text-lg tracking-[0.14em]"
        : "text-xl tracking-[0.16em]";

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <p className={`font-display font-semibold text-terminal-accent ${titleClass}`}>
          {BRAND.wordmark}
        </p>
        {showPaperBadge ? <Badge tone="warn">{BRAND.paperBadge}</Badge> : null}
      </div>
      {showSubtitle ? (
        <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-terminal-dim">
          {BRAND.subtitle}
        </p>
      ) : null}
    </div>
  );
}
