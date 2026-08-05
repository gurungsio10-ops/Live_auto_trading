# Release Readiness Report — Atlas Paper V1

**Updated:** 2026-08-05T18:30Z  
**Branch:** `release/atlas-paper-v1`  
**PR:** [#34](https://github.com/gurungsio10-ops/Live_auto_trading/pull/34)  
**Analytics:** PR #35 fast-forwarded into release tip  

## Gate snapshot (local, this pass)

| Gate | Result |
|------|--------|
| `pytest -q` (+cov≥85, precision=2) | **318 passed**, **86.38%** coverage |
| `ruff check/format` | pass |
| `mypy app` | pass |
| Frontend lint/typecheck/build | pass (prior this session) |
| Alembic empty → head | pass (`0007_perf_analytics`) |
| Alembic 0006 → head + downgrade -1 | pass |
| `docker compose config` | pass |
| Container migrate + `/health` `/ready` | pass (port 8001 evidence) |
| Gitleaks (project config) | no leaks found |
| pip-audit | no known vulns |
| npm audit (prod) | residual Next 14.x high advisories (no non-breaking 14.x bump) |
| Acceptance harness | **PASSED** (`docs/release/PAPER_V1_ACCEPTANCE_REPORT.md`) |

## Module coverage vs 90% target

| Module | Coverage | Target |
|--------|----------|--------|
| `app/accounting/invariants.py` | 90.07% | ≥90 ✓ |
| `app/services/paper_persistence.py` | 91.47% | ≥90 ✓ |
| `app/analytics/performance.py` | ~95% | ≥90 ✓ |
| `app/risk/engine.py` | 87.08% | ≥90 ✗ |
| `app/execution/paper/engine.py` | ~76% | ≥90 ✗ |

## Merge blockers for claiming 100%

1. PR #34 not yet merged into `main` (requires green Actions + merge commit).
2. Critical-module coverage below 90% for risk + paper execution engine.
3. Frontend Next.js 14.x high-severity advisories without non-breaking upgrade path.
4. Superseded PR cleanup + `v1.0.0-paper` tag after main merge.

## Authoritative docs

- `docs/release/PAPER_V1_PR_AUDIT.md`
- `docs/release/PAPER_V1_ACCEPTANCE_REPORT.md`
- `docs/release/PAPER_V1_RELEASE_NOTES.md`
- `docs/operations/DEPLOYMENT_RUNBOOK.md`
- `docs/operations/BACKUP_RESTORE.md`
