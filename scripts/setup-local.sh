#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install and start Docker Desktop first."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is unavailable. Update or restart Docker Desktop."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running. Start Docker Desktop and try again."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

random_hex() {
  openssl rand -hex 32
}

replace_setting() {
  local key="$1"
  local value="$2"
  local temporary_file
  temporary_file="$(mktemp)"
  awk -F= -v key="$key" -v value="$value" '
    BEGIN { replaced = 0 }
    $1 == key { print key "=" value; replaced = 1; next }
    { print }
    END { if (!replaced) print key "=" value }
  ' .env > "$temporary_file"
  mv "$temporary_file" .env
}

if grep -q '^ODOO_DB_PASSWORD=CHANGE_ME_' .env; then
  replace_setting ODOO_DB_PASSWORD "$(random_hex)"
fi

if grep -q '^ODOO_MASTER_PASSWORD=CHANGE_ME_' .env; then
  replace_setting ODOO_MASTER_PASSWORD "$(random_hex)"
fi

if grep -q '^N8N_DB_PASSWORD=CHANGE_ME_' .env; then
  replace_setting N8N_DB_PASSWORD "$(random_hex)"
fi

if grep -q '^N8N_ENCRYPTION_KEY=CHANGE_ME_' .env; then
  replace_setting N8N_ENCRYPTION_KEY "$(random_hex)"
fi

chmod 600 .env
mkdir -p backups shared-files

docker compose config --quiet
docker compose pull
docker compose up -d

set -a
# shellcheck disable=SC1091
. ./.env
set +a

echo
echo "GGD local services are starting:"
echo "  Odoo: http://localhost:${ODOO_LOCAL_PORT}"
echo "  n8n:  http://localhost:${N8N_LOCAL_PORT}"
echo
echo "Run ./scripts/check-local.sh after approximately one minute."
echo "Keep .env private and save its values in a password manager."

