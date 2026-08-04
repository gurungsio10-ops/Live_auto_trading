"""CORS allowlist resolution for local + Codespaces."""

from __future__ import annotations

from app.core.cors import resolve_cors_origins


def test_resolve_cors_defaults_when_empty(monkeypatch):
    monkeypatch.delenv("CODESPACE_NAME", raising=False)
    monkeypatch.delenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", raising=False)
    origins = resolve_cors_origins("")
    assert "http://127.0.0.1:3000" in origins
    assert "*" not in origins


def test_resolve_cors_keeps_configured_and_adds_codespaces(monkeypatch):
    monkeypatch.setenv("CODESPACE_NAME", "kvggrf9rpj")
    monkeypatch.setenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    origins = resolve_cors_origins("http://localhost:3000")
    assert "http://localhost:3000" in origins
    assert "https://kvggrf9rpj-3000.app.github.dev" in origins
    assert "*" not in origins


def test_resolve_cors_rejects_wildcard_entry(monkeypatch):
    monkeypatch.delenv("CODESPACE_NAME", raising=False)
    origins = resolve_cors_origins("*,http://localhost:3000")
    assert origins == ["http://localhost:3000"]
