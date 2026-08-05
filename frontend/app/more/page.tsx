"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { PaperModeBanner } from "@/components/ops/PaperModeBanner";
import { NAV_ITEMS } from "@/lib/nav";

function Row({
  href,
  label,
  icon: Icon,
  status,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  status?: string;
}) {
  return (
    <Link
      href={href}
      className="flex min-h-12 items-center gap-3 rounded-xl border border-border bg-surface-raised/40 px-3.5 py-2.5 transition hover:bg-surface-hover"
    >
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-control bg-primary-soft text-brand">
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-semibold text-foreground">{label}</span>
        {status ? <span className="block text-[12px] text-muted">{status}</span> : null}
      </span>
      <ChevronRight className="h-4 w-4 text-muted" aria-hidden />
    </Link>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
        {title}
      </h2>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

export default function MorePage() {
  const trading = NAV_ITEMS.filter((i) => i.moreTrading);
  const system = NAV_ITEMS.filter((i) => i.moreSystem);
  const info = NAV_ITEMS.filter((i) => i.moreInfo);

  return (
    <div className="space-y-5">
      <PageHeader title="More" description="Secondary Atlas tools and system controls." meta={<PaperTradingBadge />} />
      <PaperModeBanner />

      <Group title="Trading">
        {trading.map((item) => (
          <Row key={item.key} href={item.href} label={item.label} icon={item.icon} />
        ))}
      </Group>

      <Group title="System">
        {system.map((item) => (
          <Row key={item.key} href={item.href} label={item.label} icon={item.icon} />
        ))}
      </Group>

      <Group title="Information">
        {info.map((item) => (
          <Row key={item.key} href={item.href} label={item.label} icon={item.icon} />
        ))}
      </Group>
    </div>
  );
}
