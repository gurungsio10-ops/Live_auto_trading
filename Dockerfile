# Development image for Project Atlas (paper trading). Live trading remains disabled.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir -e ".[dev]"

ENV TRADING_MODE=paper \
    TRADING_ENABLED=false \
    ENABLE_LIVE_TRADING=false \
    APP_ENV=development \
    LOG_LEVEL=INFO \
    DATABASE_URL=sqlite+aiosqlite:///./atlas.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
