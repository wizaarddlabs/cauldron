import httpx
import pytest

from app import http_client


@pytest.fixture
def recorded(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client, "_client", client)
    yield calls
    monkeypatch.setattr(http_client, "_client", None)


async def test_session_merges_default_and_call_headers(recorded):
    async with http_session_with_headers() as client:
        response = await client.get(
            "https://example.test/a",
            headers={"X-Call": "1"},
        )

    assert response.json() == {"ok": True}
    assert recorded[0].headers["X-Default"] == "d"
    assert recorded[0].headers["X-Call"] == "1"


async def test_leaving_session_does_not_close_shared_pool(recorded):
    async with http_client.http_session(timeout=5) as client:
        await client.get("https://example.test/a")

    assert not http_client.get_http_client().is_closed

    async with http_client.http_session(timeout=5) as client:
        await client.head("https://example.test/b")

    assert [r.method for r in recorded] == ["GET", "HEAD"]


async def test_close_http_client_resets_pool(recorded):
    first = http_client.get_http_client()
    await http_client.close_http_client()

    assert first.is_closed
    assert http_client._client is None


def http_session_with_headers():
    return http_client.http_session(timeout=5, headers={"X-Default": "d"})
