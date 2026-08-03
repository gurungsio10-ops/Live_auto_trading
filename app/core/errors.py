"""Domain and operational exceptions for Project Atlas."""

from __future__ import annotations


class AtlasError(Exception):
    """Base application error."""


class ConfigurationError(AtlasError):
    """Invalid or unsafe configuration — fail closed, never silent fallback."""


class LiveTradingDisabledError(AtlasError, NotImplementedError):
    """Live order execution is not implemented / not enabled for this deployment."""


class KillSwitchActiveError(AtlasError):
    """New orders rejected because the emergency kill switch is active."""


class PaperResetConfirmationError(AtlasError, ValueError):
    """Paper account reset requires an explicit confirmation token."""
