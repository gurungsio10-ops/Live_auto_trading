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
    layout/             # AppShell, DesktopSidebar, MobileHeader, MobileBottomNav, GlobalStatusStrip
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
| `/` | Overview dashboard |
| `/markets` | Symbols + strategy signals |
| `/ai-decisions` | Strategy decisions / signals |
| `/portfolio` | Paper balance, equity, positions |
| `/orders` | Paper orders |
| `/activity` | Timeline of signals, risk, orders |
| `/strategies` | Strategy cards + paper controls |
| `/backtests` | Step-by-step paper backtests |
| `/risk` | Risk Centre |
| `/connection` | Backend / market / paper broker / live (disabled) |
| `/settings` | Appearance, display, read-only paper/risk |
| `/about` | Product identity + developer credit |
| `/login` | Session login |

Legacy redirects: `/positions` → `/portfolio`, `/signals` → `/ai-decisions`, `/risk-events` → `/risk`.

## Responsive behaviour

- **Desktop (≥1024px):** fixed 248px sidebar, content max-width 1600px
- **Tablet (768–1023px):** mobile header + bottom nav / more sheet
- **Mobile (<768px):** sticky top header, fixed bottom nav (Home / Markets / AI / Portfolio / More), safe-area padding

## Design tokens

Defined in `app/globals.css` (`:root`) and mapped in `tailwind.config.ts`. Prefer token utilities (`bg-surface`, `text-foreground`, `text-brand`, `border-border`) over raw hex in components.

## Data-state handling

Every API screen should support:

- Loading skeletons (`LoadingState` / `LoadingSkeleton`)
- Error + Retry (`ErrorState`)
- Empty (`EmptyState`)
- Demo / backend unavailable (`DemoBanner`)
- Missing fields shown as **Not available** / **—**

Never silently present mock data as live exchange balances.

## Paper-trading limitation

- Default and only supported execution mode in the UI is **paper**
- **PAPER TRADING** badge is shown on primary screens
- Live exchange section on Connection is explicitly **Not configured**
- No wallet connect, seed phrase, private key, or API-secret inputs

## Local run commands

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

Default local login (when auth is configured for development): `admin` / `atlas`.

Backend (separate terminal):

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or Codespaces helper: `./scripts/codespaces_start.sh`

Environment:

- `ATLAS_BACKEND_URL` — FastAPI base URL for the Next.js BFF (default `http://127.0.0.1:8000`)

## Test / quality commands

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

There is currently no dedicated frontend unit-test script in `package.json`.

Backend safety checks (repo root):

```bash
pytest -q
ruff check app tests
mypy app
```
