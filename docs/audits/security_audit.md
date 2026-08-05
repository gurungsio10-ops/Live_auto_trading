# Security Audit — Paper Consolidation Tip

**Branch:** `cursor/release-paper-v1-consolidated-e3a2`  
**Scope:** Paper-trading platform only

## Findings

| Check | Result | Notes |
|-------|--------|-------|
| Committed secrets | PASS (gitleaks CI) | `.gitleaks.toml` allowlists documented local-dev placeholders only |
| Weak default tokens | WARN | Dev defaults `admin`/`atlas` and `local-dev-admin-token` — must rotate outside local |
| Auth bypass | PASS | Mutating ops require `ADMIN_API_TOKEN`; unset → 503 fail-closed |
| CORS | PASS | Allowlist via `CORS_ALLOWED_ORIGINS` |
| SQL injection | PASS | SQLAlchemy bound params |
| Command injection | PASS | No shelling of user input on hot path |
| Path traversal | PASS | No user-controlled filesystem paths on trading APIs |
| SSRF | PASS | Webhook alert URL is operator-configured; not user-request driven |
| Insecure deserialization | PASS | No pickle of untrusted data |
| Log injection / secrets in logs | PASS | `app/core/security.py` redaction; unit tests |
| Frontend secret exposure | PASS | Admin token only in Next server BFF (`adminHeaders`) |
| Unrestricted admin routes | PASS | AdminAuthDep on mutators |
| Unsafe exceptions | PASS | AtlasError handlers; no stack traces to clients |
| Docker public by default | WARN | Compose binds Postgres/Redis locally — document firewall for cloud hosts |
| Live trading disabled | PASS | `LiveTradingGate` never allows; SafetyGuard blocks futures/leverage/withdraw |
| Direct exchange order calls | PASS | `test_security_order_paths` forbids `.create_order(` outside disabled adapter |
| AI order execution | PASS | Advisory endpoints only |

## Required operator actions (not code blockers)

1. Rotate `ADMIN_API_TOKEN` and dashboard password before any shared deployment
2. Restrict compose ports behind localhost / private network
3. Keep `TRADING_MODE=paper` and `ENABLE_LIVE_TRADING=false`

## Commands

```bash
# CI secret scan (gitleaks action)
# Local:
pytest tests/unit/test_security_order_paths.py tests/unit/test_config_security.py tests/unit/test_log_redaction.py -q
```
