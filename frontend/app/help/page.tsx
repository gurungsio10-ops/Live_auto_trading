import Link from "next/link";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionCard } from "@/components/ui/SectionCard";
import { PaperTradingBadge } from "@/components/ui/Badge";

const LINKS = [
  { href: "/about", label: "About Atlas" },
  { href: "/settings", label: "Settings" },
  { href: "/system-health", label: "System Health" },
  { href: "/kill-switch", label: "Kill Switch" },
  { href: "/risk", label: "Risk Centre" },
];

export default function HelpPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Help and Docs"
        description="How to operate Atlas in paper-trading mode."
        meta={<PaperTradingBadge />}
      />
      <SectionCard title="Paper trading only">
        <ul className="list-disc space-y-2 pl-5 text-[14px] text-secondary">
          <li>All orders are simulated. Live trading remains disabled.</li>
          <li>Every paper order passes through the central risk engine.</li>
          <li>Market data may be public-live; that does not mean real-money trading.</li>
          <li>Admin API tokens never ship to the browser — kill-switch and admin actions use BFF routes.</li>
          <li>When data is unavailable, Atlas shows Unavailable / — instead of inventing values.</li>
        </ul>
      </SectionCard>
      <SectionCard title="Useful destinations">
        <ul className="space-y-2">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="text-[14px] font-semibold text-brand hover:underline">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </SectionCard>
      <SectionCard title="Documentation in the repository">
        <p className="text-[13px] text-secondary">
          See <code className="text-foreground">frontend/README.md</code> and{" "}
          <code className="text-foreground">docs/ui/UX_GUIDELINES.md</code> for contributor guidance.
        </p>
      </SectionCard>
    </div>
  );
}
