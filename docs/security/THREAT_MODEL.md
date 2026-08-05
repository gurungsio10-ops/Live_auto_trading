# Threat Model — Project Atlas

Personal paper-trading stack. Assets: local admin control plane, paper portfolio integrity, exchange credentials (if ever configured), dashboard session secrets, and operator trust in UI state.

**Out of scope for this phase:** defending a multi-tenant SaaS or a production live trading venue connection (live submission is hard-blocked).

## Threats and mitigations

### 1. Secret exposure

**Threat:** `.env` secrets, exchange keys, `ADMIN_API_TOKEN`, `ATLAS_AUTH_SECRET`, or passwords leak via git, logs, or `/config` endpoints.

**Mitigations in code / process:**

- `.env.example` has placeholders only; real `.env` must not be committed.
- `app/core/security.redact` / `redact_settings` for safe config views (`GET /config/safe`).
- Pydantic `SecretStr` for tokens and exchange credentials.
- CI **Gitleaks** job (`.github/workflows/ci.yml` `secret-scan`).
- Structured logging expected to avoid raw secrets (covered by redaction tests).

**Residual risk:** Default dashboard credentials `admin` / `atlas` in example env — change on any shared host. Stack traces on unexpected 500s may still over-share; keep `APP_ENV` disciplined.

### 2. Unauthenticated mutators

**Threat:** Exposed API port allows kill-switch toggle, paper reset, orders, strategy start/stop without auth.

**Mitigations:**

- `AdminAuthDep` / `require_admin_token` on system and dashboard mutating routes (`X-Admin-Token` or Bearer).
- If `ADMIN_API_TOKEN` unset → **503 fail-closed** (mutators disabled).
- Constant-time compare (`secrets.compare_digest`).
- Next BFF forwards admin headers from server env — browser never needs the raw exchange secret.

**Residual risk:** Anyone who can read the Next server env or sniff localhost can call mutators. Bind APIs to localhost or a private network; do not expose without TLS and network controls.

### 3. BFF demo fallbacks

**Threat:** When FastAPI is down, Next BFF historically invented successful orders / kill-switch responses, misleading operators into thinking controls applied.

**Mitigations:**

- **Mutating** BFF routes (orders, kill-switch, and related controls) **fail closed** with HTTP 503 and no fabricated APPROVED/FILLED or fake kill-switch success.
- **Read** paths may still return demo data with `meta.demo=true` and `backend_error` so the UI can render — Demo banner must be treated as non-authoritative.
- `envelope(..., demo)` makes demo state explicit in JSON.

**Residual risk:** Operators ignoring the demo banner on read-only pages. Policy: never make risk decisions from `meta.demo=true` payloads.

### 4. Live activation / accidental live money

**Threat:** Mis-set env vars, typos, or partial checklist enable live order submission.

**Mitigations:**

- Defaults: paper mode; `ENABLE_LIVE_TRADING=false`.
- Invalid mode strings → paper (never LIVE).
- `LIVE_STARTUP_ACK` must equal `I_UNDERSTAND_LIVE_TRADING_RISKS` for checklist completeness.
- `Settings.assert_startup_safe()` rejects LIVE startup and raises `LiveTradingDisabledError` even when credentials + ack + flags are present.
- `LiveTradingGate.evaluate()` sets `allowed=False` always (`live_execution_hard_blocked`).
- `/ready` returns `not_ready` for LIVE runtime.

**Residual risk:** Future code changes that weaken the hard-block. Treat any PR that sets `allowed=True` or removes the hard-block as a security-critical review.

### 5. AI abuse

**Threat:** Advisory AI used to place orders, bypass risk, change leverage, or silently alter live config.

**Mitigations:**

- `TradingAnalyst` is structurally advisory: `advisory: true` payloads, no execution imports, documented `FORBIDDEN_ACTIONS`.
- All actionable orders still require `OrderGateway` → risk engine.
- Product copy and API description state AI is advisory only.

**Residual risk:** Future wiring of LLM tool-calling into mutators. Keep AI modules free of gateway/risk bypass imports; add tests that forbid execution imports (existing advisory tests assert labels).

## Trust boundaries

```text
[Browser] --session cookie--> [Next.js BFF] --ADMIN_API_TOKEN--> [FastAPI]
                                                                    |
                                                              Risk + Paper
                                                                    |
                                                              SQLite/Postgres
```

- Browser never holds exchange API secrets.
- Demo read data crosses the “authoritative trading state” boundary and must be labeled.

## Related

- `docs/operations/INCIDENT_RESPONSE.md`
- `docs/operations/live_trading_readiness_checklist.md`
- `app/api/deps.py`, `app/execution/live_gate.py`, `app/ai/analyst.py`
