"""Exponential backoff retry helper for provider calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class ProviderRetryError(RuntimeError):
    """Raised when retries are exhausted."""


async def with_exponential_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    jitter: float = 0.1,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except retry_exceptions as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, jitter)
            await asyncio.sleep(delay)
    raise ProviderRetryError(
        f"Provider call failed after {max_attempts} attempts: {last_exc}"
    ) from last_exc
