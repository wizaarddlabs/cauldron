import re
from pathlib import Path

import pytest
import yaml

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("*", ["*"]),
        ("https://a.example, https://b.example", ["https://a.example", "https://b.example"]),
        ('["https://a.example"]', ["https://a.example"]),
        ("", ["*"]),
    ],
)
def test_cors_origins_env_formats(monkeypatch, value, expected):
    monkeypatch.setenv("CORS_ORIGINS", value)

    assert Settings(_env_file=None).cors_origins == expected


def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert Settings(_env_file=None).cors_origins == ["*"]


def _compose_app_environment() -> dict[str, str]:
    """The app's environment from docker-compose.yml, with ${VAR:-default}
    resolved to its default as on a host whose .env sets nothing."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    environment = compose["services"]["app"]["environment"]

    def resolve(value: str) -> str:
        return re.sub(
            r"\$\{[A-Z0-9_]+(?::?-([^}]*))?\}",
            lambda m: m.group(1) or "",
            str(value),
        )

    return {key: resolve(value) for key, value in environment.items()}


def test_compose_default_environment_loads(monkeypatch):
    """Regression: CORS_ORIGINS=* from compose crashed Settings() at startup."""
    environment = _compose_app_environment()
    assert "CORS_ORIGINS" in environment

    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["*"]
    assert not settings.admin_api_key
