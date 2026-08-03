# Phase 16 — Baseline Results

Real, un-hidden results of the project's quality and test commands, run in the
configured dev environment (Python 3.12 venv, Node 22). Failures are reported
truthfully; where the repository has pre-existing debt it is called out rather
than suppressed.

Legend: PASS / FAIL / N/A (tool or file absent).

## Backend

| Command | Result | Notes |
|---|---|---|
| `pip install -e ".[dev]"` | PASS | Installs cleanly into `.venv`. |
| `ruff check .` | FAIL (pre-existing) | ~321 findings repo-wide (was 291 before Phase-15 code). **New Phase-16 files are ruff-clean.** No `[tool.ruff]` config exists; findings are default-rule style/lint on legacy code. Not mass-fixed to avoid unrelated refactoring. |
| `ruff format --check .` | FAIL (pre-existing) | 37 legacy files "would be reformatted"; 67 already formatted. **New Phase-16 files are `ruff format`-clean.** |
| `mypy app` | FAIL (pre-existing) | 21 errors in 5 files, almost all pre-existing: `app/indicators/momentum.py`, `app/strategies/ema_trend.py`, `app/backtesting/metrics.py` (`Decimal | None` arithmetic on warm-up), and `ccxt` missing stubs in `app/market_data/providers/binance.py`. **My auth module is mypy-clean.** `mypy` is not a declared dependency and there is no `[tool.mypy]` config; full typing of the legacy strategy/indicator code is out of Phase-16 scope (safety-critical, would be unrelated refactoring). |
| `pytest -q` | PASS | **122 passed** (108 pre-Phase-16 + 14 added, growing with Phase-16 tests below). |
| `alembic upgrade head` (clean DB) | PASS | Migrations `0001`→`0003` apply to an empty SQLite DB. |

## Frontend (`frontend/`)

| Command | Result | Notes |
|---|---|---|
| `npm install` | PASS | 144 packages. |
| `npm run lint` (`next lint`) | N/A (interactive) | ESLint is not configured; `next lint` prompts to configure it. Non-interactive static check used instead: `npx tsc --noEmit` → **PASS (clean)**. |
| `npm run typecheck` | N/A | No `typecheck` script; equivalent is `npx tsc --noEmit` → PASS. |
| `npm run test` | N/A | No test script/framework configured in `frontend/package.json`. |
| `npm run build` | PASS | `next build` succeeds; all routes compiled (static pages + dynamic `/api/*` proxy routes + middleware). |

## Docker

| Command | Result | Notes |
|---|---|---|
| `docker compose config` | N/A | No `docker-compose.yml` / `Dockerfile` in the repo, and Docker is not installed in this environment. Documented as a gap in the audit (§10). |

## Interpretation

- **Tests are green** (122) and the app runs; the repository is functionally **partially runnable** (see audit verdict).
- **Lint / format / type / docker acceptance criteria are not met repo-wide** because of pre-existing, un-typed, un-formatted legacy code and the absence of Docker packaging. Phase 16 does **not** mass-reformat or retype legacy safety-critical modules (that would be unrelated refactoring); new Phase-16 code is kept clean. These remain open items and are why Phase 16 is marked **in progress**, not done.

## Commands actually executed (this run)

```
pip install -e ".[dev]"        # PASS
pip install mypy               # added tool to measure baseline
ruff check .                   # 321 findings (new files clean)
ruff format --check .          # 37 legacy files would reformat (new files clean)
mypy app                       # 21 errors, 5 files (new auth module clean)
pytest -q                      # 122 passed
alembic upgrade head           # PASS on clean DB
npx tsc --noEmit  (frontend)   # PASS
```
