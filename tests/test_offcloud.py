import httpx
import pytest

from app.debrid import offcloud
from app.debrid.offcloud import OffcloudClient


class FakeAsyncClient:
    def __init__(self, *, response_data=None, sizes=None):
        self.response_data = response_data
        self.sizes = sizes or {}
        self.head_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, url):
        return httpx.Response(
            200,
            json=self.response_data,
            request=httpx.Request("GET", url),
        )

    async def head(self, url, follow_redirects=True):
        self.head_calls.append(url)
        return httpx.Response(
            200,
            headers={"Content-Length": str(self.sizes[url])},
            request=httpx.Request("HEAD", url),
        )


@pytest.mark.asyncio
async def test_list_files_fetches_sizes_and_ignores_invalid_entries(monkeypatch):
    file_urls = [
        "https://cdn.example/one.mkv",
        "https://cdn.example/two.mkv",
        42,
    ]
    clients = []

    def make_client(**kwargs):
        client = FakeAsyncClient(
            response_data=file_urls,
            sizes={
                file_urls[0]: 100,
                file_urls[1]: 200,
            },
        )
        clients.append(client)
        return client

    monkeypatch.setattr(offcloud.httpx, "AsyncClient", make_client)
    monkeypatch.setattr(offcloud.settings, "offcloud_fetch_sizes", True)
    offcloud._size_cache.clear()

    files = await OffcloudClient("key").list_files("request")

    assert [file["name"] for file in files] == ["one.mkv", "two.mkv"]
    assert [file["size"] for file in files] == [100, 200]
    assert len(clients) == 2
    assert sorted(clients[1].head_calls) == sorted(file_urls[:2])


@pytest.mark.asyncio
async def test_get_playback_link_rejects_invalid_file_index(monkeypatch):
    client = OffcloudClient("key")

    async def fake_list_files(torrent_id):
        return [{"id": "0", "name": "file.mkv", "url": "https://cdn/file"}]

    monkeypatch.setattr(client, "list_files", fake_list_files)

    with pytest.raises(ValueError, match="Invalid Offcloud file index"):
        await client.get_playback_link("request", file_index=-1)

    with pytest.raises(ValueError, match="Invalid Offcloud file index"):
        await client.get_playback_link("request", file_index=1)