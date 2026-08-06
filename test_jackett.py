import os
from app.modules.torznab import TorznabClient
from app.config import get_settings

settings = get_settings()

if not settings.jackett_url or not settings.jackett_api_key:
    print("Error: JACKETT_URL and JACKETT_API_KEY must be set in environment")
    exit(1)

client = TorznabClient(
    url=settings.jackett_url,
    api_key=settings.jackett_api_key
)

results = client.search(
    "Game.of.Thrones.S01E01"
)

for r in results[:10]:
    print("----------------")
    print(r["title"])
    print(
        "Seeds:",
        r["seeders"]
    )

