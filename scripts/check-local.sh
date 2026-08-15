#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f .env ]]; then
  echo "Missing .env. Run ./scripts/setup-local.sh first."
  exit 1
fi

docker compose config --quiet

if grep -q 'CHANGE_ME_' .env; then
  echo "One or more placeholder secrets remain in .env."
  exit 1
fi

echo "Container status:"
docker compose ps

set -a
# shellcheck disable=SC1091
. ./.env
set +a

odoo_url="http://localhost:${ODOO_LOCAL_PORT}"
n8n_url="http://localhost:${N8N_LOCAL_PORT}/healthz"

if curl --fail --silent --show-error --max-time 10 "$odoo_url" >/dev/null; then
  echo "Odoo health check: OK"
else
  echo "Odoo health check: FAILED"
  exit 1
fi

if curl --fail --silent --show-error --max-time 10 "$n8n_url" >/dev/null; then
  echo "n8n health check: OK"
else
  echo "n8n health check: FAILED"
  exit 1
fi

echo "Local foundation is healthy."

