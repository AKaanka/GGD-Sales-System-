#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f .env ]]; then
  echo "Missing .env. Run ./scripts/setup-local.sh first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="backups/${timestamp}"
mkdir -p "$destination"

echo "Creating PostgreSQL dumps..."
docker compose exec -T odoo-db \
  pg_dump --clean --if-exists --no-owner --no-privileges \
  -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME" \
  | gzip > "${destination}/odoo-database.sql.gz"

docker compose exec -T n8n-db \
  pg_dump --clean --if-exists --no-owner --no-privileges \
  -U "$N8N_DB_USER" -d "$N8N_DB_NAME" \
  | gzip > "${destination}/n8n-database.sql.gz"

echo "Archiving persistent application data..."
docker run --rm \
  -v ggd_odoo_data:/source:ro \
  -v "${project_dir}/${destination}:/backup" \
  alpine:3.20 \
  tar -czf /backup/odoo-filestore.tar.gz -C /source .

docker run --rm \
  -v ggd_n8n_data:/source:ro \
  -v "${project_dir}/${destination}:/backup" \
  alpine:3.20 \
  tar -czf /backup/n8n-data.tar.gz -C /source .

if command -v shasum >/dev/null 2>&1; then
  (cd "$destination" && shasum -a 256 ./*.gz > SHA256SUMS)
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$destination" && sha256sum ./*.gz > SHA256SUMS)
fi

chmod -R go-rwx "$destination" 2>/dev/null || true

echo "Backup created at ${destination}"
echo "Copy it to encrypted storage outside this computer."
echo "Keep the .env values separately in a password manager."

