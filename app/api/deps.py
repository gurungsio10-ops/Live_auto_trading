"""FastAPI dependencies (admin token, pagination)."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status

from app.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def require_admin_token(
    settings: SettingsDep,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """
    Protect mutating system endpoints with a local admin API token.

    Accepts ``X-Admin-Token: <token>`` or ``Authorization: Bearer <token>``.
    If ``ADMIN_API_TOKEN`` is unset, mutating endpoints are rejected (fail closed).
    """
    expected = (
        settings.admin_api_token.get_secret_value() if settings.admin_api_token else ""
    )
    if not expected.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_API_TOKEN is not configured; mutating endpoints disabled",
        )
    provided = (x_admin_token or "").strip()
    if not provided and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends()]
AdminAuthDep = Annotated[None, Depends(require_admin_token)]
