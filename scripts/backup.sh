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

local_only=0
for arg in "$@"; do
  case "$arg" in
    --local-only) local_only=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# Encryption is not optional. A dump of the whole CRM sitting in clear on the
# machine that also runs it is the finding this script exists to close (S6).
if [[ -z "${BACKUP_AGE_RECIPIENT:-}" ]]; then
  cat >&2 <<'MSG'
ABORT: BACKUP_AGE_RECIPIENT is not set, so the backup would be written in clear.

Create the key pair on a machine you trust, once:

    age-keygen -o ggd-backup.key

That file holds the PRIVATE key. It must NOT stay on this laptop: put it in
the password manager and delete the local copy. Its first line is a comment
containing the PUBLIC key, which is not secret. Put that in .env:

    BACKUP_AGE_RECIPIENT=age1........................................

Backups encrypt to the public key, so this machine can write a backup it
cannot itself read. That is the point: a laptop that is stolen gives up
nothing, and only the key in your password manager can restore.
MSG
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "ABORT: age is not installed. brew install age" >&2
  exit 1
fi

offsite="${BACKUP_OFFSITE_DIR:-}"
if [[ -z "$offsite" && "$local_only" -eq 0 ]]; then
  cat >&2 <<'MSG'
ABORT: BACKUP_OFFSITE_DIR is not set.

A copy that lives only on the production host is not a backup. Set it to a
path on an external disk or a synced folder, in .env:

    BACKUP_OFFSITE_DIR=/Volumes/GGD-Backup/ggd

Re-run with --local-only if you deliberately want a local-only backup and
understand it does not satisfy the go/no-go in GO-LIVE-PLAN section 1.2.
MSG
  exit 1
fi
if [[ -n "$offsite" && ! -d "$offsite" ]]; then
  echo "ABORT: BACKUP_OFFSITE_DIR does not exist or is not mounted: $offsite" >&2
  echo "Plug in the disk, or mount the folder, and run this again." >&2
  exit 1
fi

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

echo "Encrypting to ${BACKUP_AGE_RECIPIENT}..."
for plain in "${destination}"/*.gz; do
  age --encrypt --recipient "$BACKUP_AGE_RECIPIENT" --output "${plain}.age" "$plain"
  rm -f "$plain"
done

# Checksums cover the ciphertext, so a copy can be verified anywhere without
# the private key. Integrity and confidentiality are separate problems.
if command -v shasum >/dev/null 2>&1; then
  (cd "$destination" && shasum -a 256 ./*.age > SHA256SUMS)
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$destination" && sha256sum ./*.age > SHA256SUMS)
fi

chmod -R go-rwx "$destination" 2>/dev/null || true

if [[ -n "$offsite" ]]; then
  echo "Copying to ${offsite}..."
  mkdir -p "${offsite}/${timestamp}"
  cp "${destination}"/* "${offsite}/${timestamp}/"
  # Verify the copy where it landed, not the original. A copy that was never
  # checked at the destination is a copy nobody has tested.
  if command -v shasum >/dev/null 2>&1; then
    (cd "${offsite}/${timestamp}" && shasum -a 256 -c SHA256SUMS >/dev/null) \
      || { echo "ABORT: the off-device copy failed checksum verification." >&2; exit 1; }
  fi
  echo "Verified off-device copy at ${offsite}/${timestamp}"
fi

echo ""
echo "Backup created at ${destination}"
echo "  encrypted to : ${BACKUP_AGE_RECIPIENT}"
if [[ -n "$offsite" ]]; then
  echo "  off-device   : ${offsite}/${timestamp} (checksums verified there)"
else
  echo "  off-device   : NONE - this backup does not satisfy GO-LIVE-PLAN 1.2"
fi
echo ""
echo "Restoring needs the private key from the password manager; this machine"
echo "cannot read what it just wrote. Keep the .env values there as well."

