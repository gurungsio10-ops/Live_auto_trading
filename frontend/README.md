# Atlas Terminal (Phase 11)

Next.js + TypeScript + Tailwind operations dashboard for Project Atlas.

## Stack

- App Router pages for overview, positions, orders, signals, risk events, strategies, backtests, settings
- Recharts equity / drawdown charts
- Typed `/api/*` proxy routes → FastAPI at `http://127.0.0.1:8000` (override with `ATLAS_BACKEND_URL`)
- Demo/mock fallbacks when the backend is unavailable so the UI never blank-screens

## Develop

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Build

```bash
npm run build
npm start
```

## Safety notes

- Trading mode defaults to **paper** in demo data and settings views
- Settings page is read-only for risk limits / mode — no "go live" button
- Secrets never ship to the browser; only Next.js route handlers call FastAPI
