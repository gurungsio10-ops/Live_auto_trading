import { Shield } from "lucide-react";

/** Always-visible paper-mode safety banner for Overview and critical surfaces. */
export function PaperModeBanner({ className = "" }: { className?: string }) {
  return (
    <div
      className={[
        "flex items-start gap-3 rounded-card border border-positive/35 bg-positive-soft px-3.5 py-3",
        className,
      ].join(" ")}
      role="status"
    >
      <Shield className="mt-0.5 h-5 w-5 shrink-0 text-positive" aria-hidden />
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-positive">Paper Mode</p>
        <p className="mt-0.5 text-[13px] text-secondary">All trading is simulated</p>
      </div>
    </div>
  );
}
