#!/usr/bin/env python3
"""
Create a personal Stremio addon config from the command line, the same way the
setup page does, and print its install URL.

Configs are stored (encrypted) in /data/cauldron.db, so run this where the app's
/data volume is mounted, e.g.:

    docker compose exec app python scripts/make_config.py realdebrid YOUR_API_KEY
    docker compose exec app python scripts/make_config.py p2p

Several providers, highest priority first (add --all to list one stream per
provider instead of picking the first that has a torrent cached):

    docker compose exec app python scripts/make_config.py realdebrid KEY1 torbox KEY2

The URL's host comes from ADDON_URL.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.config_store import save_config  # noqa: E402
from app.models import DebridProvider  # noqa: E402

PROVIDERS = [provider.value for provider in DebridProvider]


def main() -> int:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        print("providers: p2p | " + " | ".join(PROVIDERS))
        return 0 if args else 1

    stream_mode = "all" if "--all" in args else "best"
    args = [arg for arg in args if arg != "--all"]

    if args == ["p2p"]:
        config = {"provider": "p2p", "api_key": None, "providers": []}
    else:
        if not args or len(args) % 2:
            print("Give each provider followed by its API key.", file=sys.stderr)
            return 1

        accounts = []
        for provider, api_key in zip(args[::2], args[1::2], strict=True):
            provider = provider.lower()
            if provider not in PROVIDERS:
                print(f"Unknown provider {provider!r}. Use: p2p | {' | '.join(PROVIDERS)}", file=sys.stderr)
                return 1
            if any(existing == provider for existing, _ in accounts):
                print(f"{provider} is listed more than once.", file=sys.stderr)
                return 1
            if not api_key.strip():
                print(f"Missing API key for {provider}.", file=sys.stderr)
                return 1
            accounts.append((provider, api_key.strip()))

        config = {
            "providers": [{"provider": p, "api_key": k} for p, k in accounts],
            "stream_mode": stream_mode,
            # First account in the single-provider fields older versions read.
            "provider": accounts[0][0],
            "api_key": accounts[0][1],
        }

    config_id = save_config(config)
    base_url = get_settings().addon_url.rstrip("/")

    print("\nAdd this addon URL in Stremio (keep it private):\n")
    print(f"  {base_url}/{config_id}/manifest.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
