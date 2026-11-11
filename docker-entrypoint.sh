#!/bin/sh
# Start Cauldron as the unprivileged "cauldron" user.
#
# /data is usually a host bind mount that existing deployments created as
# root. When started as root, take ownership of Cauldron's own files there
# (not recursively: other services may keep data under the same directory,
# e.g. ./data/zilean-postgres) and then drop privileges.
set -e

if [ "$(id -u)" = "0" ]; then
	mkdir -p /data
	chown cauldron:cauldron /data
	for path in /data/cauldron.db* /data/cauldron.key /data/ranking_preferences.json; do
		[ -e "$path" ] && chown cauldron:cauldron "$path"
	done

	exec setpriv --reuid=cauldron --regid=cauldron --init-groups "$@"
fi

exec "$@"
