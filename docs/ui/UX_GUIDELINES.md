# Project Atlas — UX Guidelines

Personal AI Trading System · Developed by Saugat Gurung

## Colour tokens

Exact starting tokens (dark professional fintech theme):

| Token | Value |
| --- | --- |
| `--background` | `#07101f` |
| `--background-secondary` | `#0a1424` |
| `--surface` | `#0e1a2d` |
| `--surface-raised` | `#122139` |
| `--surface-hover` | `#172942` |
| `--border` | `rgba(148, 163, 184, 0.14)` |
| `--border-strong` | `rgba(148, 163, 184, 0.24)` |
| `--text-primary` | `#f8fafc` |
| `--text-secondary` | `#94a3b8` |
| `--text-muted` | `#64748b` |
| `--primary` | `#5b8cff` |
| `--primary-hover` | `#729dff` |
| `--primary-soft` | `rgba(91, 140, 255, 0.14)` |
| `--positive` | `#22c55e` |
| `--positive-soft` | `rgba(34, 197, 94, 0.12)` |
| `--negative` | `#ef4444` |
| `--negative-soft` | `rgba(239, 68, 68, 0.12)` |
| `--warning` | `#f59e0b` |
| `--warning-soft` | `rgba(245, 158, 11, 0.12)` |
| `--info` | `#38bdf8` |
| `--info-soft` | `rgba(56, 189, 248, 0.12)` |

Do not scatter raw hex colours across components. Prefer CSS variables / Tailwind token classes.

Note: Tailwind `text-primary` conflicts with `bg-primary`; use **`text-foreground`** / **`text-brand`** for text.

## Typography

Font: Inter (Geist-compatible stack via `next/font`).

| Role | Size | Weight |
| --- | --- | --- |
| Page title | 22–32px (fluid) | 700 |
| Section heading | 17–20px | 600 |
| Portfolio balance | 30–48px (fluid) | 700 |
| Metric value | 20–28px | 600+ |
| Body | 14–16px | 400–500 |
| Secondary | 13–14px | 400 |

Never use body text below 12px. Apply tabular numbers to balances, percentages, prices, quantities, P/L.

## Spacing

8px system. Common values: 4, 8, 12, 16, 24, 32, 40, 48.

## Cards

- Radius: 18px (`--radius-card`)
- Border: 1px solid `var(--border)`
- Background: `var(--surface)`
- Padding: 16px mobile / 20–24px desktop
- Subtle hover border on desktop; no oversized shadows

## Buttons

- Min height 44px (primary mobile preferably 48px)
- Radius 12px
- Variants: primary (blue), secondary, warn outline, danger outline
- Never place a large filled red kill-switch button on the overview

## Inputs

- Min height 44px
- Radius 12px
- Visible labels and validation messages

## Desktop navigation

Fixed left sidebar (248px):

1. Overview  
2. Markets  
3. AI Decisions  
4. Portfolio  
5. Orders  
6. Activity  
7. Strategies  
8. Backtests  
9. Risk Centre  
10. Connection  
11. Settings  

Footer: paper status, backend status, SG avatar, Saugat Gurung credit.

## Mobile navigation

Bottom nav (exactly five): Home · Markets · AI · Portfolio · More

More links to Orders, Activity, Strategies, Backtests, Risk Centre, Connection, Settings, About.

## Status semantics

Always combine **icon + text + colour** (never colour alone):

| Concept | Values |
| --- | --- |
| Mode | Paper |
| Engine | Running / Paused / Stopped |
| System | Online / Degraded / Offline |
| Kill switch | Active / Inactive |

## Financial formatting

Utilities in `frontend/lib/format.ts`:

- Positive values include `+`
- Negative values include `−`
- Zero is neutral
- Unavailable → `—`
- Never display `NaN` / `undefined`
- GBP (£) is display preference only unless backend FX exists

## Dangerous-action patterns

- Kill switch: outlined danger control → `ConfirmDangerDialog`
- Closing positions / destructive actions: confirmation required
- Typed confirmation when backend already requires it

## Accessibility

- Semantic headings
- Keyboard navigation + visible focus rings
- Touch targets ≥ 44px
- Dialogs: Escape, focus trap, labelled
- ARIA live regions for status where practical
- `prefers-reduced-motion` respected
- Colour-independent status communication

## Copywriting rules

Prefer: Paper balance, Simulated profit, Strategy decision, Risk check approved/blocked, Trading paused, Backend unavailable, Live trading disabled, Data is stale.

Avoid: Guaranteed profit, Winning bot, Risk-free, AI predicts, Moon, Jackpot, Pump, fabricated confidence scores.

## Screenshots

Place visual QA captures here when available:

- Overview (mobile 390×844) — _pending_
- Overview (desktop 1440×900) — _pending_
- Markets mobile cards — _pending_
- Risk Centre — _pending_
- Connection (live exchange not configured) — _pending_
