import type { ReactNode } from "react";
import { SectionCard } from "./SectionCard";

/** Back-compat wrapper — prefer SectionCard. */
export function Card({
  title,
  subtitle,
  actions,
  className = "",
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <SectionCard title={title} description={subtitle} actions={actions} className={className}>
      {children}
    </SectionCard>
  );
}
