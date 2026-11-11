#!/usr/bin/env python3
"""
Create a personal Stremio addon config from the command line, the same way the
setup page does, and print its install URL.

Configs are stored (encrypted) in /data/cauldron.db, so run this where the app's
/data volume is mounted, e.g.:

    docker compose exec app python scripts/make_config.py realdebrid YOUR_API_KEY
    docker compose exec app python scripts/make_config.py p2p

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

    provider = args[0].lower()

    if provider == "p2p":
        if len(args) != 1:
            print("p2p takes no API key.", file=sys.stderr)
            return 1
        config = {"provider": "p2p", "api_key": None}
    elif provider in PROVIDERS:
        if len(args) != 2 or not args[1].strip():
            print(f"Usage: make_config.py {provider} <api_key>", file=sys.stderr)
            return 1
        config = {"provider": provider, "api_key": args[1].strip()}
    else:
        print(f"Unknown provider {provider!r}. Use: p2p | {' | '.join(PROVIDERS)}", file=sys.stderr)
        return 1

    config_id = save_config(config)
    base_url = get_settings().addon_url.rstrip("/")

    print("\nAdd this addon URL in Stremio (keep it private):\n")
    print(f"  {base_url}/{config_id}/manifest.json\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
