# Docker setup

```bash
docker compose config   # validate
docker compose up --build
```

Compose exposes the API service for paper trading. Ensure:

- `TRADING_MODE=paper`
- `ENABLE_TRADING_SCHEDULER=false` unless intentionally enabling
- `ADMIN_API_TOKEN` set for mutating routes
- Live credentials absent / unused

See root `docker-compose.yml` and `README.md`.
