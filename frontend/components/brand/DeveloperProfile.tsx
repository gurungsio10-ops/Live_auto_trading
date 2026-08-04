"use client";

import { useState } from "react";
import { BRAND } from "@/lib/brand";

export function OwnerAvatar({
  size = "sm",
  className = "",
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const dim = size === "lg" ? "h-14 w-14 text-sm" : size === "md" ? "h-10 w-10 text-xs" : "h-8 w-8 text-[10px]";

  if (failed) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary-soft font-semibold text-foreground ${dim} ${className}`}
        aria-label={BRAND.ownerName}
        title={BRAND.ownerName}
      >
        {BRAND.ownerInitials}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={BRAND.ownerImagePath}
      alt={BRAND.ownerName}
      className={`shrink-0 rounded-full border border-border object-cover ${dim} ${className}`}
      onError={() => setFailed(true)}
    />
  );
}

export function DeveloperProfile({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <OwnerAvatar size={compact ? "sm" : "md"} />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">{BRAND.ownerName}</p>
        <p className="truncate text-[12px] text-muted">{BRAND.attribution}</p>
      </div>
    </div>
  );
}
