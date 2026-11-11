#!/usr/bin/env bash
# One-shot upgrade for servers that ran the old all-in-one docker-compose.yml
# (production domain, npm_default network and ./app mount baked in).
#
# Usage, from the repository root on the server:
#
#   git pull
#   ./scripts/upgrade-vps.sh                 # recover ADDON_URL from git history
#   ./scripts/upgrade-vps.sh https://my.host # or pass it explicitly
#   ./scripts/upgrade-vps.sh --dry-run       # change files, but don't restart
#
# Safe to run more than once: existing settings are never overwritten. Re-run
# it (or `docker compose pull app && docker compose up -d`) to update to the
# latest published image.
set -euo pipefail

cd "$(dirname "$0")/.."

DRY_RUN=false
ADDON_URL_ARG=""

for arg in "$@"; do
	case "$arg" in
		--dry-run) DRY_RUN=true ;;
		-h | --help)
			sed -n '2,15p' "$0"
			exit 0
			;;
		*) ADDON_URL_ARG="$arg" ;;
	esac
done

say() { printf '==> %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 1. Host-specific compose override (port 8008, npm_default network)
# ---------------------------------------------------------------------------
if [ -f docker-compose.override.yml ]; then
	say "docker-compose.override.yml already exists; leaving it alone"
	if grep -q '\./app:/srv/app' docker-compose.override.yml; then
		echo "WARNING: docker-compose.override.yml bind-mounts ./app over the image's code." >&2
		echo "         Remove that volume line to run the published image as-is." >&2
	fi
else
	cp docker-compose.override.example.yml docker-compose.override.yml
	say "Created docker-compose.override.yml from the example"
fi

# ---------------------------------------------------------------------------
# 2. .env values that used to be hardcoded in docker-compose.yml
# ---------------------------------------------------------------------------
touch .env

env_has() { grep -qE "^[[:space:]]*$1=" .env; }

env_add() {
	# Make sure we start on a new line, then append KEY=VALUE.
	if [ -s .env ] && [ "$(tail -c1 .env)" != "" ]; then
		printf '\n' >>.env
	fi
	printf '%s=%s\n' "$1" "$2" >>.env
	say "Added $1=$2 to .env"
}

if env_has ADDON_URL; then
	say "ADDON_URL already set in .env; leaving it alone"
else
	addon_url="$ADDON_URL_ARG"

	if [ -z "$addon_url" ]; then
		# The commit that removed the hardcoded value; its parent still has it.
		removed_in=$(git log --format=%H -n1 -S'ADDON_URL: https' -- docker-compose.yml 2>/dev/null || true)
		if [ -n "$removed_in" ]; then
			addon_url=$(git show "${removed_in}^:docker-compose.yml" 2>/dev/null |
				sed -n 's/^[[:space:]]*ADDON_URL:[[:space:]]*\(https\?:[^[:space:]]*\).*/\1/p' |
				head -n1 || true)
		fi
	fi

	if [ -z "$addon_url" ]; then
		echo "Could not determine ADDON_URL. Re-run with it, e.g.:" >&2
		echo "  ./scripts/upgrade-vps.sh https://cauldron.example.com" >&2
		exit 1
	fi

	env_add ADDON_URL "$addon_url"
fi

# Zilean now only starts with the "full" profile.
if [ -d zilean ]; then
	if env_has COMPOSE_PROFILES; then
		say "COMPOSE_PROFILES already set in .env; leaving it alone"
	else
		env_add COMPOSE_PROFILES full
	fi
else
	say "No ./zilean checkout found; Zilean services stay disabled"
fi

# ---------------------------------------------------------------------------
# 3. Sanity checks
# ---------------------------------------------------------------------------
if ! docker network inspect npm_default >/dev/null 2>&1; then
	echo "WARNING: docker network 'npm_default' does not exist." >&2
	echo "         Edit docker-compose.override.yml if your proxy uses another network." >&2
fi

docker compose config -q
say "Compose configuration is valid"

# ---------------------------------------------------------------------------
# 4. Pull the published image and restart
# ---------------------------------------------------------------------------
if $DRY_RUN; then
	say "Dry run: skipping 'docker compose pull app && docker compose up -d'"
	exit 0
fi

if docker compose pull app; then
	docker compose up -d
else
	echo "WARNING: could not pull the Cauldron image; building from this checkout instead." >&2
	docker compose up -d --build
fi
say "Done. Check: docker compose ps && curl -fsS http://127.0.0.1:8008/ready"
