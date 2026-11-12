import re

import pytest
from fastapi.testclient import TestClient

import app.config_store as config_store
from app.api.stremio import _normalize_debrid_config
from app.main import app
from app.web import routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "DB", tmp_path / "cauldron.db")
    return TestClient(app)


def _config_id(html: str) -> str:
    return re.search(r"/([0-9a-f]{32})/manifest\.json", html).group(1)


def test_no_provider_creates_p2p_addon(client):
    response = client.post("/generate", data={"provider": "p2p", "resolution": "1080p"})

    assert response.status_code == 200
    assert "Install in Stremio" in response.text
    assert "streams play directly over P2P" in response.text
    config = config_store.load_config(_config_id(response.text))
    assert config["provider"] == "p2p"
    assert config["api_key"] is None


def test_p2p_config_ignores_server_torrin_key(monkeypatch):
    monkeypatch.setattr(
        "app.api.stremio.get_settings",
        lambda: type("S", (), {"torrin_api_key": "server-key"})(),
    )

    assert _normalize_debrid_config({"provider": "p2p"}) == (None, None)


def test_provider_with_key_is_saved(client):
    response = client.post(
        "/generate",
        data={"provider": "realdebrid", "api_key": "  rd-key  "},
    )

    assert response.status_code == 200
    config = config_store.load_config(_config_id(response.text))
    assert (config["provider"], config["api_key"]) == ("realdebrid", "rd-key")
    assert "your Real-Debrid account" in response.text


def test_provider_without_key_is_rejected_and_keeps_selections(client):
    response = client.post(
        "/generate",
        data={"provider": "torbox", "api_key": "", "resolution": "720p", "cached_only": "on"},
    )

    assert response.status_code == 400
    assert "Enter your TorBox API key" in response.text
    assert "/manifest.json" not in response.text
    # The user's choices survive the error.
    assert re.search(r'value="720p" checked', response.text)
    assert not re.search(r'value="1080p" checked', response.text)
    assert re.search(r'<option value="torbox" selected>', response.text)


def test_unknown_provider_is_rejected(client):
    response = client.post("/generate", data={"provider": "evil", "api_key": "x"})

    assert response.status_code == 400
    assert "Unknown debrid provider" in response.text


def test_result_is_not_put_in_the_url(client):
    response = client.post("/generate", data={"provider": "p2p"}, follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers
    assert response.headers["cache-control"] == "no-store"


def test_install_link_uses_stremio_scheme(client):
    response = client.post(
        "/generate",
        data={"provider": "p2p"},
        headers={"host": "cauldron.example", "x-forwarded-proto": "https"},
    )

    config_id = _config_id(response.text)
    assert f'href="stremio://cauldron.example/{config_id}/manifest.json"' in response.text


def test_legacy_per_provider_fields_still_work(client):
    response = client.post("/generate", data={"torbox_key": "tb", "premiumize_key": "pm"})

    config = config_store.load_config(_config_id(response.text))
    assert (config["provider"], config["api_key"]) == ("torbox", "tb")


def test_home_never_prefills_api_keys(client, monkeypatch):
    from app.ranking.preferences import RankingPreferences

    prefs = RankingPreferences()
    prefs.torbox_key = "LEAKED-SHARED-KEY"
    monkeypatch.setattr(routes, "load_preferences", lambda: prefs)

    response = client.get("/")

    assert response.status_code == 200
    assert "LEAKED-SHARED-KEY" not in response.text
    assert 'name="api_key"' in response.text


def test_configure_redirects_to_home(client):
    response = client.get("/configure", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/"


def test_privacy_note_only_for_debrid_addons(client):
    p2p = client.post("/generate", data={"provider": "p2p"})
    debrid = client.post("/generate", data={"provider": "torbox", "api_key": "k"})

    assert "use your debrid account" not in p2p.text
    assert "use your debrid account" in debrid.text


def test_language_lists_pin_unknown_multi_dubbed_and_offer_leechers(client):
    html = client.get("/").text

    for group in ("required_languages", "preferred_languages", "excluded_languages"):
        values = re.findall(rf'name="{group}" value="([a-z]+)"', html)
        assert values[:3] == ["unknown", "multi", "dubbed"]
        assert values.count("multi") == 1

    assert 'data-value="leechers"' in html
    assert "#privacy--security" in html
