#!/usr/bin/env python3
"""
Generate the base64url config segment used in the personal Stremio addon
install URL: https://your-host/<config>/manifest.json

Usage:
    python scripts/make_config.py realdebrid YOUR_API_KEY
"""
import base64
import json
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/make_config.py <provider> <api_key>")
        print("providers: realdebrid | alldebrid | premiumize | torbox")
        sys.exit(1)

    provider, api_key = sys.argv[1], sys.argv[2]
    payload = json.dumps({"provider": provider, "api_key": api_key}).encode()
    config = base64.urlsafe_b64encode(payload).decode().rstrip("=")

    print("\nAdd this to your Stremio addon URL:\n")
    print(f"  http://localhost:8000/{config}/manifest.json\n")


if __name__ == "__main__":
    main()
