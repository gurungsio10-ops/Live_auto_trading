# Security Runbook (Paper)

## Defaults

- `TRADING_MODE=paper`
- `ENABLE_LIVE_TRADING=false`
- Mutating endpoints require `ADMIN_API_TOKEN`
- CORS allowlist via `CORS_ALLOWED_ORIGINS`

## Rotate admin token

1. Generate a new random token
2. Set `ADMIN_API_TOKEN` on API and Next.js server env
3. Restart both processes
4. Confirm mutating calls with old token return 401

## Kill switch

```bash
curl -X POST http://127.0.0.1:8000/api/v1/system/kill-switch/activate \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"incident"}'
```

## Suspected credential leak

1. Rotate credentials immediately
2. Activate kill switch
3. Pause scheduler
4. Review journal / kill_switch_events / audit rows
5. Keep recon halt until healthy

## Frontend

Never put `ADMIN_API_TOKEN` in `NEXT_PUBLIC_*` or client bundles. BFFs use server-side `adminHeaders()`.

## References

- `SECURITY.md`
- `docs/security/THREAT_MODEL.md`
- `docs/audits/security_audit.md`
