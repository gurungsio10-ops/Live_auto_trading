"use client";

import { useState } from "react";
import { BRAND } from "@/lib/brand";

type Size = "sm" | "md" | "lg";

const sizes: Record<Size, string> = {
  sm: "h-8 w-8 text-[10px]",
  md: "h-10 w-10 text-xs",
  lg: "h-14 w-14 text-sm",
};

/**
 * Circular owner avatar. Uses /saugat-gurung.jpg when present;
 * falls back to initials "SG" if the image is missing or fails to load.
 */
export function OwnerAvatar({
  size = "sm",
  className = "",
}: {
  size?: Size;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        className={[
          "inline-flex shrink-0 items-center justify-center rounded-full border border-terminal-accent/40 bg-terminal-accent/10 font-display font-semibold tracking-wide text-terminal-accent",
          sizes[size],
          className,
        ].join(" ")}
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
      width={size === "lg" ? 56 : size === "md" ? 40 : 32}
      height={size === "lg" ? 56 : size === "md" ? 40 : 32}
      className={[
        "shrink-0 rounded-full border border-terminal-border object-cover",
        sizes[size],
        className,
      ].join(" ")}
      onError={() => setFailed(true)}
    />
  );
}
