# Backup and Isolated Restore Drill — current procedure

> ## What happened on 1 September, and what changed
>
> The first version of this drill **damaged the live system**. It isolated by
> `COMPOSE_PROJECT_NAME`, which assumes Compose prefixes volume names with the
> project. `compose.yaml` pins explicit names:
>
> ```yaml
> volumes:
>   odoo_db_data:
>     name: ggd_odoo_db_data
> ```
>
> Compose does **not** prefix those. The drill stack got its own containers and
> ports but mounted the **live volumes**, so the `dropdb`, the restore and the
> workflow deactivation all ran against live data. Live n8n lost its
> owner/settings rows and fell back to the "Set up owner account" screen. It
> was recovered by restoring `backups/20260901T164244Z` with only the live
> stack running and `psql -v ON_ERROR_STOP=1`. Odoo was unaffected beyond
> cleared sessions. The printed `docker compose down -v` teardown would have
> deleted the live volumes outright; it was never run.
>
> **Three fixes, all now in place:**
>
> 1. `compose.restore.yaml` redefines all four volumes to `ggd_restore_*`
>    names. The drill stack physically cannot mount live storage.
> 2. The script **proves** it before writing anything: it runs `docker inspect`
>    on every drill container, prints the volumes each one mounts, and aborts
>    if any live volume name appears. It then stops, and only restores when
>    re-run with `--confirm`.
> 3. Every `psql` runs with `-v ON_ERROR_STOP=1`. Without it a half-applied
>    restore reports success, which is how the original damage went unnoticed.
>
> Isolation by project name is not isolation. Verify the volumes.

## How to run it

Two steps, on purpose. The first proves the isolation and restores nothing:

```bash
cd "/Users/kaan/Desktop/GGD -Sales-System "
./scripts/gate5-restore-drill.sh                # prints the volume proof, then stops
./scripts/gate5-restore-drill.sh --confirm      # only after you have read the proof
```

### Restoring from the encrypted off-device copy

Since finding S6, backups are encrypted with `age` and copied off the laptop,
so the drill's input is a directory of `*.age` files that must be decrypted
first. Bring the private key in from the password manager, and drill against
the **off-device copy** rather than the local one — restoring from the copy on
the production host proves only that the host can read its own disk.

```bash
./scripts/decrypt-backup.sh /Volumes/GGD-Backup/ggd/<timestamp> ~/ggd-backup.key
# prints the directory it decrypted into
./scripts/gate5-restore-drill.sh "<that directory>"            # proof only
./scripts/gate5-restore-drill.sh --confirm "<that directory>"  # the restore
rm -rf "<that directory>" ~/ggd-backup.key                     # afterwards
```

`decrypt-backup.sh` verifies the checksums before the key is used at all, so a
corrupted copy is caught without ever being decrypted. If verification fails,
do not decrypt it — fetch another copy. The decrypted directory is a readable
copy of the whole CRM: delete it, and the key file, when the drill is done.

The proof looks like this — every mount must be a `ggd_restore_*` volume:

```
ggd-restore-test-odoo-db-1 -> ggd_restore_odoo_db_data
ggd-restore-test-odoo-1    -> ggd_restore_odoo_data
PROOF: no live volume (ggd_odoo_db_data ggd_odoo_data ...) is mounted
```

If any live volume name appears there, the script aborts before writing
anything. It never tears down, and its teardown command targets only the
`ggd_restore_*` volumes. The manual phases below remain the reference, and the
two browser checks at the end still need a human.

## A restored copy shares real credentials

The restored stack decrypts the same Zoho SMTP/IMAP, Anthropic and Odoo
credentials as live, because it uses the same `N8N_ENCRYPTION_KEY`. Anything
that activates in there acts for real.

Checked against the 1 September backup: nothing in it can self-start. The only
two active workflows are `GGD-00` and the legacy `GGD 99`, both error-trigger
handlers with no send node, and error triggers only fire when another workflow
in the same instance fails. The legacy `GGD 04` carries a published version id
but its `active` flag is false and its only trigger is manual. So the practical
risk here is low — but the script still forces every restored workflow inactive
before starting n8n, because "low" depends on a fact about today's backup that
a future backup could quietly change.

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

Every line must read `OK`. Verified this way on 1 September for both the
20 August backup and the fresh `20260901T164244Z` one — all four archives OK
in each.

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
`.local/share/Odoo/filestore/<db>`. **Every archive so far contains both**, so
this is not a legacy-archive-only problem — the fresh backup taken on
1 September has it too:

| Archive | `./filestore/` | `./.local/share/Odoo/filestore/` |
| --- | --- | --- |
| `20260820T111048Z` | 104 entries | 112 entries |
| `20260901T164244Z` | 878 entries | 112 entries |

The legacy tree has not grown since August — nothing new writes there — but it
still holds 112 files that the current `data_dir` tree does not, so both must
land and then be consolidated. Skipping this gives a
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

### Runs

| Date | Backup | Source | Result |
| --- | --- | --- | --- |
| 1 Sep 2026 | `20260901T...` | local, unencrypted | passed (Gate 5) |
| 4 Sep 2026 | `20260904T182932Z` | **encrypted, off-device copy** | passed |

The 4 September run is the one that closes finding S6. The backup was
encrypted with `age`, copied to a second location, verified by checksum *at
the destination*, decrypted there with the private key, and restored into
isolated `ggd_restore_*` volumes. It is the first drill to exercise the path
that would actually be used if this laptop were lost.

Restored against live at the time of the backup:

| Check | Restored | Live | |
| --- | --- | --- | --- |
| `crm_lead` rows | 66 | 66 | match |
| of those active | 48 | 48 | match |
| n8n workflows | 18 | 18 | match |
| n8n credentials | 5 | 5 | match |
| n8n users | 1 | 1 | match |

All four live volumes were present after teardown and all four
`ggd_restore_*` volumes were removed.

Two things about this run are worth knowing rather than assuming:

- It was performed with a **throwaway key pair**, generated to exercise the
  mechanism and destroyed immediately after, along with the decrypted copy and
  the backup made under it. **No backup currently on disk is readable**, because
  the real key pair has not been created yet — that step is Kaan's, and until it
  is done the go/no-go in `GO-LIVE-PLAN.md` section 1.2 is not met.
- The script's printed expectations (`[expect: 41 total, of which 25 active]`)
  are hard-coded from 1 September and are now stale. The counts above were
  checked against the live database directly. A drill whose expectations drift
  cannot distinguish "the data grew" from "the restore was partial".
