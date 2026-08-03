# Project Atlas

Gated paper/live crypto trading system. **Paper mode is the default.** Live
trading requires every condition in `docs/architecture/roadmap.md` simultaneously.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Safety

- `TRADING_MODE` defaults to `paper`
- All orders pass through `app/risk/engine.py`
- Use `Decimal` for money; UTC for timestamps
- Never log secrets — use `app/core/security.redact`

See `.cursor/rules/atlas.mdc` and `docs/architecture/roadmap.md`.
