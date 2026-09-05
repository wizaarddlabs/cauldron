from app.api.stremio import _normalize_debrid_config


def test_saved_provider_does_not_fall_back_to_server_provider(monkeypatch):
    monkeypatch.setattr(
        "app.api.stremio.get_settings",
        lambda: type("Settings", (), {"torrin_api_key": "server-key"})(),
    )

    assert _normalize_debrid_config(
        {"provider": "premiumize", "api_key": None}
    ) == ("premiumize", None)