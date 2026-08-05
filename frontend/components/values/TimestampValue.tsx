"use client";

import { formatRelativeTime, formatTs } from "@/lib/format";

export function TimestampValue({
  value,
  relative = false,
  className = "",
  compact = false,
}: {
  value: string;
  relative?: boolean;
  className?: string;
  compact?: boolean;
}) {
  const full = formatTs(value);
  const display = relative ? formatRelativeTime(value) : compact ? full.slice(5, 16) : full;
  return (
    <time dateTime={value} title={full} className={`text-[13px] text-muted tabular ${className}`}>
      {display}
    </time>
  );
}
