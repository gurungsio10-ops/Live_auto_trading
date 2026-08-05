# Mobile UI Audit — Project Atlas (`release/atlas-paper-v1`)

**Date:** 2026-08-05 (UTC)  
**Branch tip:** post-consolidation mobile IA on paper tip (#28 lineage)

## Navigation IA

| Item | Route | Notes |
|------|-------|-------|
| Home | `/` | Overview priorities, ops strip, scheduler, kill switch |
| Trade | `/orders` | Order ticket + history (cards on mobile) |
| Positions | `/positions` | Expandable cards &lt; `md`, table ≥ `md` |
| Activity | `/activity` | Fills / signals / risk feed |
| More | `/more` | Secondary ops + About attribution |

- Bottom nav: fixed, `lg:hidden`, touch targets ≥ 44×44 px (`data-testid="mobile-bottom-nav"`).
- Desktop sidebar: `hidden lg:flex` (`data-testid="desktop-sidebar"`).
- No “Go Live” control anywhere in primary IA.
- Attribution: “Project Atlas — Developed by Saugat Gurung” (`AtlasFooter`).

## Viewport results (Playwright + system Chrome)

Evidence: `docs/evidence/mobile-viewports/home-{width}.png` and `viewport-results.json`.  
Command: `node frontend/scripts/capture-viewports.mjs` (API login, then Home).

| Width | Bottom nav | Sidebar | Horizontal overflow | Screenshot |
|------:|:----------:|:-------:|:-------------------:|------------|
| 320 | visible | hidden | none | `home-320.png` |
| 375 | visible | hidden | none | `home-375.png` |
| 390 | visible | hidden | none | `home-390.png` |
| 430 | visible | hidden | none | `home-430.png` |
| 768 | visible | hidden | none | `home-768.png` |
| 1024 | hidden | visible | none | `home-1024.png` |
| 1440 | hidden | visible | none | `home-1440.png` |

Static contract: `node frontend/scripts/check-mobile-nav.mjs` → `mobile_nav_contract_ok`.

## Home (mobile) priority checklist

Observed on captured Home viewports:

- [x] PAPER / TESTNET / LIVE DISABLED badges (`OpsStatusStrip`)
- [x] Backend connected / disconnected
- [x] Portfolio balance + equity + P&L tiles (`tabular-nums`)
- [x] Active positions count
- [x] Risk / system status panel
- [x] Scheduler running/stopped + Start/Stop controls
- [x] Kill switch active/inactive + control
- [x] Recent execution activity (after cycle)
- [x] Skeleton / error / empty states preserved via existing Loading/Error/Empty components
- [x] Fail-closed BFF behaviour unchanged (503 + `backend_error`, no invented fills)

## Remaining UI polish (non-blocking)

- Dense action button wrap on very narrow widths is functional but busy; consider collapsing secondary actions into a sheet later.
- Positions short label is `Pos` in bottom nav to fit 320 px.
- Premium visual redesign from PRs #29–#33 was **not** merged wholesale (backend CI red / divergent APIs); IA concepts were ported onto the #28 tip.
