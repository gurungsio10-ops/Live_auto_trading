"use client";

import Link from "next/link";
import { MORE_LINKS } from "@/lib/nav";
import { AtlasFooter } from "@/components/layout/AtlasFooter";
import { Card } from "@/components/ui/Card";

export default function MorePage() {
  return (
    <div className="min-w-0 space-y-4" data-testid="more-page">
      <div>
        <h1 className="font-display text-2xl tracking-[0.08em] uppercase">More</h1>
        <p className="mt-1 text-xs text-terminal-dim">
          Recovery, strategies, settings, and about — paper operations only.
        </p>
      </div>

      <Card title="Operations">
        <ul className="divide-y divide-terminal-border/70">
          {MORE_LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="flex min-h-[44px] items-center justify-between px-1 py-3 font-display text-sm uppercase tracking-[0.1em] text-terminal-text hover:text-terminal-accent"
              >
                <span>{link.label}</span>
                <span className="text-terminal-dim" aria-hidden>
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Safety">
        <ul className="space-y-2 text-[12px] font-mono text-terminal-dim">
          <li>Default mode: PAPER</li>
          <li>ENABLE_LIVE_TRADING: false</li>
          <li>Live order submission: impossible</li>
          <li>Futures / margin / leverage / withdrawals: disabled</li>
          <li>AI: advisory only — cannot bypass risk engine</li>
          <li>No “Go Live” control in this UI</li>
        </ul>
      </Card>

      <Card title="About">
        <p className="text-sm text-terminal-text">Project Atlas</p>
        <p className="mt-2 text-[12px] text-terminal-dim">
          Deterministic personal paper-trading platform. Simulated fills only.
        </p>
        <AtlasFooter className="mt-4 border-t border-terminal-border !px-0 !text-left" />
      </Card>
    </div>
  );
}
