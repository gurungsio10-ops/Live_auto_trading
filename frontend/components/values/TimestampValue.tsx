"use client";

import { formatTs, formatTsShort } from "@/lib/format";

export function TimestampValue({
  value,
  compact = false,
  className = "",
}: {
  value: string;
  compact?: boolean;
  className?: string;
}) {
  const full = formatTs(value);
  const display = compact ? formatTsShort(value) : full;
  return (
    <time
      dateTime={value}
      title={full}
      className={`inline-block whitespace-nowrap font-mono text-xs text-terminal-dim tabular-nums ${className}`}
    >
      {display}
    </time>
  );
}
