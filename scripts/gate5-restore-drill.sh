#!/usr/bin/env bash
# DISABLED 1 September 2026 — this script was UNSAFE and caused live damage.
#
# WHY IT WAS WRONG
# ----------------
# It isolated the drill with COMPOSE_PROJECT_NAME, assuming Compose would
# prefix volume names with the project. compose.yaml pins EXPLICIT volume
# names:
#
#     volumes:
#       odoo_db_data:
#         name: ggd_odoo_db_data
#
# Compose does not prefix explicitly named volumes. The "isolated" stack got
# its own containers and ports but mounted the LIVE volumes, so the dropdb,
# the database restore and the "UPDATE workflow_entity SET active = false"
# all ran against live data. It also printed a `docker compose down -v`
# teardown command that would have deleted the live volumes outright.
#
# The container-name guard it carried was worthless: containers were isolated,
# storage was not.
#
# BEFORE ANY REPLACEMENT IS WRITTEN, the isolation must be proven at the
# VOLUME level, not the project level. Either:
#   * give the restore stack its own compose file with different volume names
#     (ggd_restore_odoo_data, ...), or
#   * run the drill on a machine or VM that cannot see the live volumes at all.
# And verify with `docker volume ls` plus `docker inspect` on the actual
# containers that not one live volume is mounted, before restoring anything.
#
# Other defects worth carrying into any replacement:
#   * psql must run with -v ON_ERROR_STOP=1. Without it a half-applied
#     restore reports success.
#   * the live stack must be stopped, or provably untouched, during a restore.
#   * teardown must never be printed as a copy-pasteable `down -v`.
#
# The manual procedure in docs/RESTORE-DRILL.md has the same volume flaw and
# carries the same warning.

echo "This script is DISABLED. It mounted the LIVE volumes and caused damage." >&2
echo "Read the comments at the top of this file before writing a replacement." >&2
exit 1
