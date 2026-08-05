import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { PaperTradingBadge } from "@/components/ui/Badge";
import { DeveloperProfile } from "@/components/brand/DeveloperProfile";
import { BRAND } from "@/lib/brand";

export default function AboutPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        title="About"
        description="Project purpose, mode and developer credit."
        meta={<PaperTradingBadge />}
      />
      <SectionCard>
        <h2 className="page-title">{BRAND.name}</h2>
        <p className="mt-1 text-secondary">{BRAND.subtitle}</p>
        <p className="mt-4 text-sm text-secondary">
          Purpose: personal research, testing and strategy evaluation using simulated paper trading.
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          <span className="rounded-control border border-border bg-surface-raised px-3 py-1.5 text-secondary">
            Mode: Paper trading
          </span>
          <span className="rounded-control border border-border bg-surface-raised px-3 py-1.5 text-secondary">
            Live trading disabled
          </span>
          <span className="rounded-control border border-border bg-surface-raised px-3 py-1.5 text-secondary">
            Version: {BRAND.version}
          </span>
          <span className="rounded-control border border-border bg-surface-raised px-3 py-1.5 text-secondary">
            Environment: development
          </span>
        </div>
      </SectionCard>
      <SectionCard title="Developer">
        <DeveloperProfile />
        <p className="mt-3 text-sm text-muted">{BRAND.attribution}</p>
        <p className="mt-1 text-sm text-muted">{BRAND.ownerName}</p>
      </SectionCard>
    </div>
  );
}
