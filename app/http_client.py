"""
Shared, pooled HTTP client.

Every outbound request (scrapers, debrid providers, metadata lookups) goes
through one ``httpx.AsyncClient`` so TCP/TLS connections are reused instead of
being re-established on every call. Connection limits come from the
``HTTPX_MAX_CONNECTIONS`` / ``HTTPX_MAX_KEEPALIVE_CONNECTIONS`` settings.

Call sites use :func:`http_session` exactly like they used
``httpx.AsyncClient``::

    async with http_session(timeout=15, headers={...}) as client:
        response = await client.get(url)

The session only carries per-call defaults (timeout, headers, redirects);
leaving the ``async with`` block does not close the shared pool.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

_UNSET: Any = object()

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the process-wide pooled client, creating it on first use."""
    global _client

    if _client is None or _client.is_closed:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=settings.scrape_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.httpx_max_connections,
                max_keepalive_connections=settings.httpx_max_keepalive_connections,
            ),
        )

    return _client


async def close_http_client() -> None:
    """Close the pooled client (called on application shutdown)."""
    global _client

    if _client is not None and not _client.is_closed:
        await _client.aclose()

    _client = None


class HttpSession:
    """Per-call defaults layered over the shared pooled client."""

    def __init__(
        self,
        *,
        timeout: Any = _UNSET,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = False,
    ) -> None:
        self._timeout = timeout
        self._headers = dict(headers or {})
        self._follow_redirects = follow_redirects

    async def __aenter__(self) -> HttpSession:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._timeout is not _UNSET:
            kwargs.setdefault("timeout", self._timeout)

        kwargs.setdefault("follow_redirects", self._follow_redirects)

        if self._headers:
            kwargs["headers"] = {**self._headers, **(kwargs.get("headers") or {})}

        return await get_http_client().request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("HEAD", url, **kwargs)


def http_session(
    *,
    timeout: Any = _UNSET,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = False,
) -> HttpSession:
    return HttpSession(
        timeout=timeout,
        headers=headers,
        follow_redirects=follow_redirects,
    )
