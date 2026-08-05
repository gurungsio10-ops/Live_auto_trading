# Disaster recovery (paper)

1. Activate kill switch
2. Stop scheduler (`POST /api/trading/stop` with `STOP_PAPER_TRADING`)
3. Snapshot/backup the database file or Postgres volume
4. Run reconciliation; keep halted on mismatch
5. Restore from backup if materialised state is corrupt
6. Hydrate via process restart (`bootstrap_paper_runtime`)
7. Only reset paper account with admin token + `RESET_PAPER_ACCOUNT` when intentional

Live money recovery is out of scope — live execution is disabled.
