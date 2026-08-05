"""CORS origin resolution for local + GitHub Codespaces dashboards."""

from __future__ import annotations

import os


def resolve_cors_origins(configured: str | None) -> list[str]:
    """
    Build the allowlist for browser origins.

    Always includes configured origins. When running in GitHub Codespaces,
    also adds the forwarded HTTPS frontend origin so optional direct browser
    calls (and preflights) succeed. Never returns ``*`` when credentials are used.
    """
    origins: list[str] = []
    for part in (configured or "").split(","):
        value = part.strip().rstrip("/")
        if value and value != "*":
            origins.append(value)

    codespace = (os.getenv("CODESPACE_NAME") or "").strip()
    domain = (
        os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN") or "app.github.dev"
    ).strip()
    if codespace and domain:
        origins.append(f"https://{codespace}-3000.{domain}")

    # Local defaults when nothing configured.
    if not origins:
        origins = ["http://127.0.0.1:3000", "http://localhost:3000"]

    # Preserve order, drop duplicates.
    return list(dict.fromkeys(origins))
