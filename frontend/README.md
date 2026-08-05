# Project Atlas — Frontend

Next.js + TypeScript + Tailwind dashboard for **Project Atlas** — Personal AI Trading System (paper trading).

Developed by Saugat Gurung.

## Stack

- Next.js App Router
- TypeScript (strict)
- Tailwind CSS with CSS design tokens
- Recharts for equity / drawdown charts
- Lucide React icons
- Typed `/api/*` BFF proxy routes → FastAPI (`ATLAS_BACKEND_URL`, default `http://127.0.0.1:8000`)
- Demo/mock fallbacks when the backend is unavailable (always labelled **Demo data**)

## UI architecture

```
frontend/
  app/                  # Routes + BFF API handlers
  components/
    layout/             # AppShell, DesktopSidebar, MobileHeader, MobileBottomNav, MobileDrawer
    ops/                # PaperModeBanner, HeroEquityCard, MetricCard, SystemStatusCard, SignalCard, OrderCard, RiskMeter, SegmentTabs
    overview/           # PortfolioHero, EngineStatusCard, SafetyControls
    cards/              # PositionCard, DecisionCard, MarketCard, etc.
    ui/                 # SectionCard, PageHeader, Badge, Button, dialogs, states
    values/             # MoneyValue, PnlValue, PercentageValue, QuantityValue, TimestampValue
    charts/             # EquityCurveChart, DrawdownChart
    brand/              # DeveloperProfile / SG avatar
  lib/
    api-client.ts       # Browser fetch to /api/*
    backend.ts          # Server-side FastAPI client
    format.ts           # Money / % / qty / relative time
    nav.ts              # Desktop + mobile navigation map
    status.ts           # Engine / system status mapping
    types.ts            # Domain types mirrored from backend
```

## Route map

| Route | Purpose |
| --- | --- |
| `/` | Overview (paper banner, equity hero, metrics, system status, signals, activity) |
| `/positions` | Open / Closed paper positions |
| `/orders` | Open / History / Cancelled paper orders + ticket |
| `/signals` | Strategy signals with filters |
| `/more` | Grouped secondary navigation |
| `/risk` | Risk Centre with usage meters |
| `/risk-events` | Risk event audit list |
| `/kill-switch` | Dedicated kill-switch control (confirmation + phrase) |
| `/journal` | Redirects to `/audit` |
| `/help` | Help and docs |
| `/strategies` | Strategy cards + paper controls |
| `/backtests` | Step-by-step paper backtests |
| `/scheduler` | Paper scheduler controls |
| `/system-health` | Backend / DB / market / scheduler posture |
| `/settings` | Appearance, display, read-only paper/risk |
| `/about` | Product identity + developer credit |
| `/portfolio` | Legacy portfolio deep-dive (equity charts) |
| `/ai-decisions` | Legacy signals view |
| `/markets` | Symbols + strategy signals |
| `/activity` | Timeline of signals, risk, orders |
| `/connection` | Backend / market / paper broker / live (disabled) |
| `/login` | Session login |

## Responsive behaviour

- **Desktop (≥1024px):** collapsible left sidebar, multi-column grids, tables where useful
- **Tablet (768–1023px):** mobile header + bottom nav
- **Mobile (<768px):** compact ATLAS header, side drawer, fixed bottom nav (**Overview / Positions / Orders / Signals / More**), safe-area padding

## Design tokens

Defined in `app/globals.css` (`:root`) and mapped in `tailwind.config.ts`. Prefer token utilities (`bg-surface`, `text-foreground`, `text-brand`, `border-border`) over raw hex in components.

## Data-state handling

Every API screen should support:

- Loading skeletons (`LoadingState` / `LoadingSkeleton`)
- Error + Retry (`ErrorState`)
- Empty (`EmptyState`)
- Demo / backend unavailable (`DemoBanner`)
- Missing fields shown as **Not available** / **—** / **Unavailable**

Never silently present mock data as live exchange balances. Never invent equity charts, fills, orders, or confidence values.

Risk score on Overview / Risk Centre is **derived client-side** from kill switch, pause, drawdown and daily loss versus configured limits — labelled as derived.

## Commands

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test --if-present
npm --prefix frontend run build
npm --prefix frontend run dev
```

Login demo credentials: `admin` / `atlas` (see auth BFF).
