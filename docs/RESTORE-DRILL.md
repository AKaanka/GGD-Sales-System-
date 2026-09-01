# Backup and Isolated Restore Drill — current procedure

Written 1 September 2026 for Gate 5. This supersedes
[SECTION-C-BACKUP-RESTORE.md](SECTION-C-BACKUP-RESTORE.md) as the procedure to
follow. That file is kept as the August record of the drill as it was designed
then; it is **not** safe to follow verbatim today. Three things in it no longer
match the system, all three verified against the live repo on 1 September:

1. **The backup format changed.** It expects a single
   `~/backups/20260818T*.tar.gz` to `tar -xzf`, containing `odoo-dump.sql` and
   `n8n-dump.sql`. `scripts/backup.sh` actually writes a *directory*,
   `backups/<UTC timestamp>/`, holding `odoo-database.sql.gz`,
   `n8n-database.sql.gz`, `odoo-filestore.tar.gz`, `n8n-data.tar.gz` and
   `SHA256SUMS`. There is no combined archive to extract.
2. **It renames the databases inconsistently.** It sets
   `ODOO_DB_NAME=ggd_restore_test` but then restores into `odoo_restore_test`.
   The procedure below keeps the database names identical to live instead, and
   isolates by Compose project name and host port, which is simpler and removes
   the class of error entirely.
3. **It never creates the Odoo database.** The dump is taken with
   `pg_dump --clean --if-exists` and contains no `CREATE DATABASE`
   (verified: zero matches). `odoo-db` starts with `POSTGRES_DB: postgres`, so
   the target database does not exist in a fresh stack and `psql` has nothing
   to restore into.

## Safety rules

- The drill runs in its **own Compose project**, in `~/ggd-restore-test`. Never
  run `docker compose down -v` (or any volume removal) from the real project
  directory: that destroys the live `odoo_db_data`, `odoo_data`, `n8n_db_data`
  and `n8n_data` volumes.
- The live stack keeps running throughout. The drill only ever *reads* the
  backup files.
- Copy `.env` as-is. Do not print it, and do not regenerate
  `N8N_ENCRYPTION_KEY` — the restored n8n must decrypt its credentials with the
  same key, which is the point of the credential check in Phase 4.

## Phase 0 — Pre-checks

```bash
cd /path/to/GGD-Sales-System
df -h .                 # need a couple of GB free for the second stack
docker compose ps       # live stack up and healthy
```

Disk was at 91% (23 GB free) on 1 September, which is enough. It was 98%
(5.9 GB) on 27 August — if it has crept back up, clear space *before* starting,
not during.

## Phase 1 — Fresh backup

```bash
./scripts/backup.sh
BK="backups/$(ls -t backups | head -1)"; echo "$BK"
ls -lh "$BK"
( cd "$BK" && shasum -a 256 -c SHA256SUMS )
```

Every line must read `OK`. (The 20 August backup was verified this way on
1 September: all four archives OK.)

## Phase 2 — Isolated stack

```bash
mkdir -p ~/ggd-restore-test && cd ~/ggd-restore-test
cp /path/to/GGD-Sales-System/compose.yaml .
cp /path/to/GGD-Sales-System/.env .
```

Edit only these three lines in the **copied** `.env` (add
`COMPOSE_PROJECT_NAME` if it is not already there):

```
COMPOSE_PROJECT_NAME=ggd-restore-test
ODOO_LOCAL_PORT=8070
N8N_LOCAL_PORT=5679
```

Leave `ODOO_DB_NAME`, `N8N_DB_NAME`, both DB users and passwords, and
`N8N_ENCRYPTION_KEY` exactly as they are. The distinct project name gives this
stack its own containers and its own volumes, so nothing collides with live.

```bash
docker compose up -d
sleep 30
docker compose ps        # all services up
```

## Phase 3 — Restore

Set `BK` to the **absolute** path of the backup directory from Phase 1, then:

```bash
cd ~/ggd-restore-test
set -a; . ./.env; set +a          # so $ODOO_DB_NAME etc. are available

# Odoo database — must be created first, the dump does not create it
docker compose exec -T odoo-db createdb -U "$ODOO_DB_USER" "$ODOO_DB_NAME" || true
gzip -dc "$BK/odoo-database.sql.gz" \
  | docker compose exec -T odoo-db psql -q -U "$ODOO_DB_USER" -d "$ODOO_DB_NAME"

# n8n database — created automatically by the postgres image (POSTGRES_DB)
gzip -dc "$BK/n8n-database.sql.gz" \
  | docker compose exec -T n8n-db psql -q -U "$N8N_DB_USER" -d "$N8N_DB_NAME"
```

### Filestore — including the consolidation that is easy to miss

`scripts/start-odoo.sh` sets `data_dir = /var/lib/odoo`, so the live filestore
is `/var/lib/odoo/filestore/<db>`. Archives that predate that setting use
`.local/share/Odoo/filestore/<db>`. **The 20 August archive contains both**
(verified: `./filestore/ggd/` 104 entries, `./.local/share/Odoo/filestore/ggd/`
112 entries), so both must land and then be consolidated. Skipping this gives a
server that runs with a blank white UI — assets 404 and the logs do not
obviously say why.

```bash
docker compose cp "$BK/odoo-filestore.tar.gz" odoo:/tmp/fs.tar.gz
docker compose exec -T -u root odoo bash -lc '
  cd /var/lib/odoo && tar -xzf /tmp/fs.tar.gz &&
  if [ -d .local/share/Odoo/filestore ]; then
    cp -rn .local/share/Odoo/filestore/. filestore/ ;
  fi &&
  chown -R odoo:odoo /var/lib/odoo && rm -f /tmp/fs.tar.gz'
```

Keep `.local/...` in place until Phase 4 passes; it is the fallback if the copy
missed something.

```bash
docker compose restart odoo n8n
sleep 20
```

## Phase 4 — Verification

Odoo on <http://127.0.0.1:8070>, n8n on <http://127.0.0.1:5679>.

Expected values, as measured on live on 1 September:

| Check | Expected |
| --- | --- |
| `ggd_crm` module | installed, `19.0.1.8.0` |
| Installed modules | 76 |
| CRM leads | 25 |
| Non-`.invalid` lead addresses | 3 (FX4, the review-inbox holder, one `example.com`) |
| n8n workflows | 18 |
| n8n credentials | 5 — Header Auth, SMTP, IMAP, Anthropic, Odoo |

- The Odoo UI must render **with styling**. A blank white page means the
  filestore consolidation above did not take.
- Open each restored n8n credential and confirm it opens and reports as
  connected/decryptable. **Do not reveal or print the values** — the check is
  that n8n can still decrypt them with the restored `N8N_ENCRYPTION_KEY`, not
  what they contain.
- Do **not** publish or execute any workflow in the restored stack. It shares
  real credentials with live, so an activated send workflow there would send
  real mail.

## Phase 5 — Teardown

```bash
cd ~/ggd-restore-test      # confirm you are HERE, not in the live project
docker compose down -v
cd ~ && rm -rf ~/ggd-restore-test
```

`docker compose ps` in the live project must still show the live stack
untouched.

## Recording the result

Gate 5 passes when Phases 1–4 are green. Record in `NEXT-ACTIONS.txt` and
`docs/PROJECT-STATUS.md`: the backup timestamp used, checksum result, the six
verification values actually observed, and confirmation that the live volumes
were never touched.
