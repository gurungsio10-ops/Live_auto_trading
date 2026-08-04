import { BRAND } from "@/lib/brand";
import { OwnerAvatar } from "./OwnerAvatar";

export function DeveloperAttribution({
  showAvatar = false,
  className = "",
}: {
  showAvatar?: boolean;
  className?: string;
}) {
  return (
    <p
      className={[
        "flex items-center gap-2 text-[10px] font-mono text-terminal-dim",
        className,
      ].join(" ")}
    >
      {showAvatar ? <OwnerAvatar size="sm" /> : null}
      <span>{BRAND.attribution}</span>
    </p>
  );
}
