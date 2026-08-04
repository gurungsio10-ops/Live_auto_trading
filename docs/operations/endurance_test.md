# Endurance test

```bash
source .venv/bin/activate
pytest -q tests/integration/test_endurance_paper_replay.py
```

The test:

- builds ≥30 days of deterministic 1h candles
- runs paper cycles with duplicate submissions
- persists + hydrates mid-run (restart simulation)
- asserts no duplicate fill IDs, cash≥0, fill qty ≤ order qty
- requires reconciliation healthy at the end
