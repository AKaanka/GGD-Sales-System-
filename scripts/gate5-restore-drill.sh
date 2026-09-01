#!/usr/bin/env bash
# Gate 5, steps 4-5: isolated restore drill.
#
# Restores a backup into a SEPARATE Compose project (~/ggd-restore-test) with
# its own containers, volumes and ports, then verifies the restored data.
#
# It deliberately does NOT tear down. Teardown deletes volumes, and this script
# will not run a volume deletion for you - it prints the command instead.
#
# The live stack is never touched: every compose command runs from the test
# directory, and the script aborts if the containers it is about to act on do
# not belong to the ggd-restore-test project.
#
# Usage: ./scripts/gate5-restore-drill.sh [backup-dir]     (default: newest)

set -uo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

TEST_PROJECT="ggd-restore-test"
TEST_DIR="$HOME/ggd-restore-test"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$project_dir/backups/gate5-restore-drill-${ts}.log"

backup_arg="${1:-}"
if [ -n "$backup_arg" ]; then
  BK="$(cd "$backup_arg" && pwd)"
else
  newest="$(ls -t backups | grep -E '^[0-9]{8}T[0-9]{6}Z$' | head -1)"
  BK="$project_dir/backups/$newest"
fi

fail() { echo "ABORT: $*" >&2; exit 1; }

{
echo "GGD Gate 5 restore drill — ${ts}"
echo "Backup: $BK"
echo "======================================================================"

for f in odoo-database.sql.gz n8n-database.sql.gz odoo-filestore.tar.gz SHA256SUMS; do
  [ -f "$BK/$f" ] || fail "missing $f in $BK"
done

echo
echo "### 1. Verify the backup before trusting it"
( cd "$BK" && { shasum -a 256 -c SHA256SUMS 2>/dev/null || sha256sum -c SHA256SUMS; } ) \
  || fail "checksum verification failed - do not restore this backup"

echo
echo "### 2. Build the isolated project"
mkdir -p "$TEST_DIR"
[ "$TEST_DIR" != "$project_dir" ] || fail "test dir equals the live project dir"
cp "$project_dir/compose.yaml" "$TEST_DIR/"
cp "$project_dir/.env" "$TEST_DIR/.env"

python3 - "$TEST_DIR/.env" "$TEST_PROJECT" <<'PY'
import sys
path, proj = sys.argv[1], sys.argv[2]
want = {"COMPOSE_PROJECT_NAME": proj, "ODOO_LOCAL_PORT": "8070", "N8N_LOCAL_PORT": "5679"}
lines = open(path).read().splitlines()
seen = set()
out = []
for line in lines:
    k = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else None
    if k in want:
        out.append(f"{k}={want[k]}"); seen.add(k)
    else:
        out.append(line)
for k, v in want.items():
    if k not in seen:
        out.append(f"{k}={v}")
open(path, "w").write("\n".join(out) + "\n")
print("isolation applied:", ", ".join(f"{k}={v}" for k, v in want.items()))
PY
[ $? -eq 0 ] || fail "could not write the isolated .env"

cd "$TEST_DIR" || fail "cannot enter $TEST_DIR"
set -a; . ./.env; set +a
[ "${COMPOSE_PROJECT_NAME:-}" = "$TEST_PROJECT" ] || fail "COMPOSE_PROJECT_NAME is not $TEST_PROJECT"

echo
echo "### 3. Start the isolated stack"
docker compose up -d || fail "compose up failed"

names="$(docker compose ps --format '{{.Name}}' | tr '\n' ' ')"
echo "containers: $names"
case "$names" in
  *"$TEST_PROJECT"*) : ;;
  *) fail "containers do not belong to $TEST_PROJECT - refusing to continue" ;;
esac

echo "waiting for databases..."
for i in $(seq 1 30); do
  docker compose exec -T odoo-db pg_isready -U "$ODOO_DB_USER" >/dev/null 2>&1 && \
  docker compose exec -T n8n-db  pg_isready -U "$N8N_DB_USER"  >/dev/null 2>&1 && break
  sleep 2
done

echo
echo "### 4. Restore both databases"
docker compose stop odoo n8n >/dev/null 2>&1
docker compose exec -T odoo-db dropdb   --if-exists -U "$ODOO_DB_USER" "$ODOO_DB_NAME" || true
docker compose exec -T odoo-db createdb              -U "$ODOO_DB_USER" "$ODOO_DB_NAME" || true
gzip -dc "$BK/odoo-database.sql.gz" \
  | docker compose exec -T odoo-db psql -q -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME" >/dev/null \
  && echo "RESULT: odoo database restored" || echo "RESULT: odoo database restore FAILED"
gzip -dc "$BK/n8n-database.sql.gz" \
  | docker compose exec -T n8n-db  psql -q -U "$N8N_DB_USER"  -d "$N8N_DB_NAME" >/dev/null \
  && echo "RESULT: n8n database restored"  || echo "RESULT: n8n database restore FAILED"

echo
echo "### 5. Belt and braces: no workflow starts itself in the restored copy"
# The 1 Sep backup contains nothing that could self-start (the only active
# workflows are error-trigger handlers with no send node), but a restored copy
# shares REAL credentials with live, so this stays unconditional.
docker compose exec -T n8n-db psql -q -U "$N8N_DB_USER" -d "$N8N_DB_NAME" \
  -c 'UPDATE workflow_entity SET active = false, "activeVersionId" = NULL;' \
  && echo "RESULT: all restored workflows forced inactive"

echo
echo "### 6. Filestore, including the consolidation step"
docker compose up -d odoo n8n >/dev/null 2>&1
sleep 10
docker compose cp "$BK/odoo-filestore.tar.gz" odoo:/tmp/fs.tar.gz || echo "RESULT: filestore copy FAILED"
docker compose exec -T -u root odoo bash -lc '
  cd /var/lib/odoo && tar -xzf /tmp/fs.tar.gz &&
  if [ -d .local/share/Odoo/filestore ]; then
    cp -rn .local/share/Odoo/filestore/. filestore/ 2>/dev/null || true;
    echo "consolidated legacy filestore tree";
  fi &&
  chown -R odoo:odoo /var/lib/odoo && rm -f /tmp/fs.tar.gz' \
  && echo "RESULT: filestore restored" || echo "RESULT: filestore restore FAILED"

docker compose restart odoo n8n >/dev/null 2>&1
sleep 20

echo
echo "### 7. Verification"
q() { docker compose exec -T odoo-db psql -tA -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME" -c "$1" 2>/dev/null | tr -d '\r'; }
n() { docker compose exec -T n8n-db  psql -tA -U "$N8N_DB_USER"  -d "$N8N_DB_NAME"  -c "$1" 2>/dev/null | tr -d '\r'; }

echo "ggd_crm module        : $(q "select state||' '||latest_version from ir_module_module where name='ggd_crm';")   [expect: installed 19.0.1.8.0]"
echo "installed modules     : $(q "select count(*) from ir_module_module where state='installed';")   [expect: 76]"
echo "crm leads             : $(q "select count(*) from crm_lead;")   [expect: 25]"
echo "non-.invalid addresses: $(q "select count(*) from crm_lead where email_from is not null and email_from not like '%.invalid';")   [expect: 3]"
echo "n8n workflows         : $(n "select count(*) from workflow_entity;")   [expect: 18]"
echo "n8n credentials       : $(n "select count(*) from credentials_entity;")   [expect: 5]"
echo "n8n active workflows  : $(n "select count(*) from workflow_entity where active;")   [expect: 0, forced above]"

echo
echo "Manual checks that cannot be scripted safely:"
echo "  a) open http://127.0.0.1:${ODOO_LOCAL_PORT} - it must render WITH styling."
echo "     A blank white page means the filestore consolidation did not take."
echo "  b) open http://127.0.0.1:${N8N_LOCAL_PORT}, open one credential, and confirm"
echo "     it opens without an encryption-key error. Do NOT reveal the values -"
echo "     the check is that n8n can still decrypt them, not what they contain."

echo
echo "======================================================================"
echo "The drill did NOT tear anything down. When you are finished:"
echo
echo "    cd $TEST_DIR && docker compose down -v && cd ~ && rm -rf $TEST_DIR"
echo
echo "Run that ONLY from $TEST_DIR. The same command in the live project"
echo "directory would delete the live Odoo and n8n volumes."
} 2>&1 | tee "$log"

echo
echo "Log written to: $log"
