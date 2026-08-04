import { Lock } from "lucide-react";

export function LockedSettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/70 py-2.5 text-[14px] last:border-0">
      <span className="inline-flex items-center gap-2 text-secondary">
        <Lock className="h-3.5 w-3.5" aria-hidden />
        {label}
        <span className="sr-only">Read only</span>
      </span>
      <span className="truncate text-right font-medium tabular text-foreground" title={value}>
        {value}
      </span>
    </div>
  );
}
