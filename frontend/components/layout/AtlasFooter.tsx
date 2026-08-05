/**
 * Compact attribution — name only, no contact details.
 */
export function AtlasFooter({ className = "" }: { className?: string }) {
  return (
    <footer
      data-testid="atlas-footer"
      className={[
        "border-t border-terminal-border/80 px-4 py-3 text-center text-[10px] font-mono text-terminal-dim",
        className,
      ].join(" ")}
    >
      Project Atlas — Developed by Saugat Gurung
    </footer>
  );
}
