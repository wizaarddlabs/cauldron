import hashlib
import re

from fastapi.testclient import TestClient

from app.main import app
from app.web import routes


def test_page_assets_carry_their_current_content_hash():
    html = TestClient(app).get("/").text

    references = re.findall(r'(?:href|src)="(/static/[^"?]+)\?v=([0-9a-f]+)"', html)
    names = {path.removeprefix("/static/") for path, _ in references}
    assert {"style.css", "settings.js", "cauldron.png"} <= names

    for path, version in references:
        content = (routes.STATIC_DIR / path.removeprefix("/static/")).read_bytes()
        assert version == hashlib.sha256(content).hexdigest()[:10], path

    # No hand-maintained ?v=N left behind.
    assert not re.search(r"/static/[^\"']+\?v=\d+[\"']", html)


def test_asset_url_changes_when_file_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "STATIC_DIR", tmp_path)
    routes._asset_hash.cache_clear()
    (tmp_path / "app.js").write_text("one")
    first = routes.asset_url("app.js")

    routes._asset_hash.cache_clear()
    (tmp_path / "app.js").write_text("two")
    second = routes.asset_url("app.js")

    routes._asset_hash.cache_clear()
    assert first != second
    assert first.startswith("/static/app.js?v=")


def test_served_asset_matches_url():
    client = TestClient(app)
    html = client.get("/").text
    script = re.search(r'src="(/static/settings\.js\?v=[0-9a-f]+)"', html).group(1)

    body = client.get(script).text
    assert "initProviderRows" in body
