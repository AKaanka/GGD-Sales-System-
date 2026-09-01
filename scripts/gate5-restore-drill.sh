#!/usr/bin/env bash
# Gate 5, steps 4-5: isolated restore drill.
#
# HISTORY: the first version of this script mounted the LIVE volumes and
# damaged the live system on 1 September 2026. It isolated by
# COMPOSE_PROJECT_NAME, but compose.yaml pins explicit volume names, which
# Compose does not prefix. This version fixes that at the volume level using
# compose.restore.yaml, and PROVES it before touching anything.
#
# Two-step by design:
#   ./scripts/gate5-restore-drill.sh              # start + prove isolation, then STOP
#   ./scripts/gate5-restore-drill.sh --confirm    # same, then actually restore
#
# It never tears down and never runs `down -v`.

set -uo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

PROJ="ggd-restore-test"
TEST_DIR="$HOME/ggd-restore-test"
LIVE_VOLUMES="ggd_odoo_db_data ggd_odoo_data ggd_n8n_db_data ggd_n8n_data"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$project_dir/backups/gate5-restore-drill-${ts}.log"

fail() { echo "ABORT: $*" >&2; exit 1; }

# Argument parsing is deliberately strict. Interactive zsh does NOT treat '#'
# as a comment, so a pasted "script.sh --confirm  # note" arrives here as real
# arguments. Anything that is not --confirm and not an existing directory is a
# mistake, and this stops rather than guessing.
CONFIRM=0
BK_ARG=""
skip_rest=0
for a in "$@"; do
  [ "$skip_rest" = 1 ] && continue
  case "$a" in
    --confirm) CONFIRM=1 ;;
    \#*) skip_rest=1 ;;                       # a pasted trailing comment: ignore it and the rest
    -*) fail "unknown option '$a' (only --confirm is accepted)" ;;
    *)  if [ -d "$a" ]; then BK_ARG="$a"
        else fail "'$a' is not a directory. Pass a backup directory, or nothing to use the newest."; fi ;;
  esac
done

if [ -n "$BK_ARG" ]; then
  BK="$(cd "$BK_ARG" && pwd)"
else
  newest="$(ls -t backups 2>/dev/null | grep -E '^[0-9]{8}T[0-9]{6}Z$' | head -1)"
  [ -n "$newest" ] || fail "no backup directory found under backups/"
  BK="$project_dir/backups/$newest"
fi
[ -d "$BK" ] || fail "backup directory does not exist: $BK"

dc() { docker compose -f compose.yaml -f compose.restore.yaml -p "$PROJ" --env-file "$TEST_DIR/.env" "$@"; }

{
echo "GGD Gate 5 restore drill — ${ts}"
echo "Backup: $BK"
echo "Mode:   $([ "$CONFIRM" = 1 ] && echo 'RESTORE (--confirm given)' || echo 'PROVE ISOLATION ONLY')"
echo "======================================================================"

[ -f compose.restore.yaml ] || fail "compose.restore.yaml missing - it is what keeps this off live storage"
for f in odoo-database.sql.gz n8n-database.sql.gz odoo-filestore.tar.gz SHA256SUMS; do
  [ -f "$BK/$f" ] || fail "missing $f in $BK"
done

echo
echo "### 1. Verify the backup before trusting it"
( cd "$BK" && { shasum -a 256 -c SHA256SUMS 2>/dev/null || sha256sum -c SHA256SUMS; } ) \
  || fail "checksum verification failed - do not restore this backup"

echo
echo "### 2. Drill environment (ports and project name only; volumes come from the override)"
mkdir -p "$TEST_DIR"
cp "$project_dir/.env" "$TEST_DIR/.env"
python3 - "$TEST_DIR/.env" <<'PY'
import sys
path = sys.argv[1]
want = {"ODOO_LOCAL_PORT": "8070", "N8N_LOCAL_PORT": "5679"}
lines = open(path).read().splitlines(); seen=set(); out=[]
for line in lines:
    k = line.split("=",1)[0].strip() if "=" in line and not line.strip().startswith("#") else None
    if k in want: out.append(f"{k}={want[k]}"); seen.add(k)
    else: out.append(line)
for k,v in want.items():
    if k not in seen: out.append(f"{k}={v}")
open(path,"w").write("\n".join(out)+"\n")
print("drill ports: ODOO=8070 N8N=5679")
PY
[ $? -eq 0 ] || fail "could not write the drill .env"

echo
echo "### 3. Start the drill stack"
dc up -d || fail "compose up failed"
sleep 5

echo
echo "### 4. PROVE the drill cannot see live storage"
mounted=""
for c in $(dc ps -q); do
  name="$(docker inspect -f '{{.Name}}' "$c" | tr -d '/')"
  vols="$(docker inspect -f '{{range .Mounts}}{{if .Name}}{{.Name}} {{end}}{{end}}' "$c")"
  echo "  $name -> ${vols:-<none>}"
  mounted="$mounted $vols"
done
for lv in $LIVE_VOLUMES; do
  case " $mounted " in
    *" $lv "*) fail "drill container mounts LIVE volume $lv - stopping before any write" ;;
  esac
done
echo "PROOF: no live volume ($LIVE_VOLUMES) is mounted by any drill container."

if [ "$CONFIRM" != 1 ]; then
  echo
  echo "Isolation proven. Nothing was restored."
  echo "Re-run with --confirm to perform the restore:"
  echo "    ./scripts/gate5-restore-drill.sh --confirm"
  exit 0
fi

echo
echo "### 5. Restore both databases (ON_ERROR_STOP=1 - a partial restore must fail loudly)"
set -a; . "$TEST_DIR/.env"; set +a
dc stop odoo n8n >/dev/null 2>&1
for i in $(seq 1 30); do dc exec -T odoo-db pg_isready -U "$ODOO_DB_USER" >/dev/null 2>&1 && break; sleep 2; done
dc exec -T odoo-db dropdb --if-exists -U "$ODOO_DB_USER" "$ODOO_DB_NAME" || true
dc exec -T odoo-db createdb          -U "$ODOO_DB_USER" "$ODOO_DB_NAME" || fail "createdb failed"
gzip -dc "$BK/odoo-database.sql.gz" \
  | dc exec -T odoo-db psql -q -v ON_ERROR_STOP=1 -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME" >/dev/null \
  && echo "RESULT: odoo database restored" || fail "odoo restore FAILED"
gzip -dc "$BK/n8n-database.sql.gz" \
  | dc exec -T n8n-db psql -q -v ON_ERROR_STOP=1 -U "$N8N_DB_USER" -d "$N8N_DB_NAME" >/dev/null \
  && echo "RESULT: n8n database restored" || fail "n8n restore FAILED"

echo
echo "### 6. Force every restored workflow inactive (it shares real credentials)"
dc exec -T n8n-db psql -q -v ON_ERROR_STOP=1 -U "$N8N_DB_USER" -d "$N8N_DB_NAME" \
  -c 'UPDATE workflow_entity SET active = false, "activeVersionId" = NULL;' \
  && echo "RESULT: restored workflows forced inactive"

echo
echo "### 7. Filestore, with the legacy-tree consolidation"
dc up -d odoo n8n >/dev/null 2>&1
sleep 15
dc cp "$BK/odoo-filestore.tar.gz" odoo:/tmp/fs.tar.gz || fail "filestore copy failed"
dc exec -T -u root odoo bash -lc '
  cd /var/lib/odoo && tar -xzf /tmp/fs.tar.gz &&
  if [ -d .local/share/Odoo/filestore ]; then cp -rn .local/share/Odoo/filestore/. filestore/ 2>/dev/null || true; fi &&
  chown -R odoo:odoo /var/lib/odoo && rm -f /tmp/fs.tar.gz' \
  && echo "RESULT: filestore restored and consolidated" || echo "RESULT: filestore restore FAILED"
dc restart odoo n8n >/dev/null 2>&1
sleep 20

echo
echo "### 8. Verification (raw SQL: counts include archived rows)"
q() { dc exec -T odoo-db psql -tA -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME" -c "$1" 2>/dev/null | tr -d '\r'; }
n() { dc exec -T n8n-db  psql -tA -U "$N8N_DB_USER"  -d "$N8N_DB_NAME"  -c "$1" 2>/dev/null | tr -d '\r'; }
echo "ggd_crm module      : $(q "select state||' '||latest_version from ir_module_module where name='ggd_crm';")   [expect: installed 19.0.1.8.0]"
echo "installed modules   : $(q "select count(*) from ir_module_module where state='installed';")   [expect: 76]"
echo "crm_lead rows       : $(q "select count(*) from crm_lead;")   [expect: 41 total, of which 25 active]"
echo "  of those active   : $(q "select count(*) from crm_lead where active;")   [expect: 25]"
echo "n8n workflows       : $(n "select count(*) from workflow_entity;")   [expect: 18]"
echo "n8n credentials     : $(n "select count(*) from credentials_entity;")   [expect: 5]"
echo "n8n users           : $(n "select count(*) from \"user\";")   [expect: 1 - this is what a broken restore loses]"

echo
echo "Then check by eye:"
echo "  a) http://127.0.0.1:${ODOO_LOCAL_PORT} renders WITH styling (blank = filestore step failed)"
echo "  b) http://127.0.0.1:${N8N_LOCAL_PORT} opens one credential without an encryption-key error."
echo "     Do NOT reveal the values."

echo
echo "======================================================================"
echo "Teardown (safe: these volumes are the drill's own, not live):"
echo
echo "    docker compose -f compose.yaml -f compose.restore.yaml -p $PROJ --env-file $TEST_DIR/.env down -v"
echo "    rm -rf $TEST_DIR"
echo
echo "That -v deletes only ggd_restore_* volumes. Verify with: docker volume ls | grep ggd_"
} 2>&1 | tee "$log"

echo
echo "Log written to: $log"
