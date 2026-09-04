# Operations, Backup, and Migration

## Availability

The local system runs only while Docker Desktop and the computer are running. Disable computer sleep during a controlled test window, but do not treat a laptop as a permanent production server.

## Backup contents

The backup script creates:

- `odoo-database.sql.gz`
- `odoo-filestore.tar.gz`
- `n8n-database.sql.gz`
- `n8n-data.tar.gz`
- `SHA256SUMS`, when a supported checksum command is available

The Odoo database and filestore are a pair; restore them from the same backup timestamp.

**Filestore location.** Odoo stores files under the configured `data_dir`.
`scripts/start-odoo.sh` sets `data_dir = /var/lib/odoo`, so the active filestore is
`/var/lib/odoo/filestore/<db>`. Archives taken before that setting existed contain
the default layout `.local/share/Odoo/filestore/<db>` instead. After restoring an
older archive, consolidate the two into the `data_dir` path before starting Odoo:

The following is **not** a command to run directly in the macOS host terminal.
Run it only inside an isolated restoration Odoo container where the restored
Odoo volume is mounted at `/var/lib/odoo`:

```
cp -rn /var/lib/odoo/.local/share/Odoo/filestore/<db>/. /var/lib/odoo/filestore/<db>/
```

Replace `<db>` with the restored database name and inspect both directories
before copying. Keep the old directory until the isolated restore has passed
its checks. Never run this consolidation against the working local instance.

Skipping this produces a running server whose web UI is blank, because asset
requests fail with `FileNotFoundError` and no CSS or JS is served.

The `.env` is intentionally not copied into the backup. Save its values separately in a password manager. In particular, preserve `N8N_ENCRYPTION_KEY`.

## Backup schedule

- During development: after every material configuration change.
- During active CRM use: daily.
- Before image updates: always.
- Before VPS migration: final backup after stopping writes.

At least one backup must live outside the computer running the stack.

### Encryption and the off-device copy

`scripts/backup.sh` encrypts every artifact with [age](https://age-encryption.org)
and copies the result off the machine. It refuses to run without both, because
an unencrypted dump of the whole CRM on the host that also serves it is the
defect this replaced (finding S6), and a copy that lives only on that host is
not a backup.

Two values in `.env`:

| Variable | What it is |
| --- | --- |
| `BACKUP_AGE_RECIPIENT` | the **public** half of an age key pair. Not secret. |
| `BACKUP_OFFSITE_DIR` | an external disk or synced folder the copy is written to. |

Create the pair once, on a machine you trust:

```bash
age-keygen -o ggd-backup.key
```

That file is the **private key**. Put it in the password manager and delete the
local copy — it must not live on this laptop, or the encryption protects
nothing against the case it exists for. The file's first line is a comment
carrying the public key; that string goes in `BACKUP_AGE_RECIPIENT`.

The machine therefore writes backups it cannot read. A stolen laptop gives up
nothing, and only the key in the password manager can restore.

The checksums cover the ciphertext, so any copy can be verified anywhere
without the private key. `backup.sh` verifies the off-device copy *where it
landed* rather than the original, since a copy nobody checked at the
destination is a copy nobody has tested.

### Restoring

```bash
./scripts/decrypt-backup.sh <backup-dir> <identity-file> [output-dir]
```

It verifies the checksums *before* the key is used, decrypts, and writes fresh
checksums over the plaintext so `gate5-restore-drill.sh` works on the result
unchanged. Bring the private key in from the password manager for the restore
and delete both it and the decrypted directory afterwards — that directory is
a readable copy of the entire CRM, which is precisely what the encryption
exists to prevent.

If a backup fails checksum verification, do not decrypt it. Fetch another copy.

## Updates

Never update Odoo and n8n blindly.

1. Create a backup.
2. Record the currently running image versions.
3. Read release notes and breaking changes.
4. Pull one application update at a time.
5. Start and check logs.
6. Test login, CRM records, credentials, and a non-sending workflow.
7. Roll back to the prior image if validation fails.

An Odoo major-version change is a database migration project, not a normal container refresh. Keep Odoo on major version 19 until a planned migration is tested.

The starter kit pins both applications to explicit image versions. Treat a
change to `ODOO_VERSION` or `N8N_VERSION` as an update: back up first and test
the new version before keeping it.

## Known issues

Both of these were found on 18 August 2026 and share a shape: **the system
reports success, and the truth is different.** Neither raises an error, so
neither is visible from a status field or a green execution.

### Deactivating a workflow can silently fail

**What happens.** A workflow's stored `active` flag reads `false`, the UI shows
it switched off, and the schedule trigger keeps firing anyway. Observed on
`GGD 98t`: seven consecutive one-minute executions while the flag read `false`,
each one caught by the shared error handler.

**Why it matters.** The rule that every workflow stays inactive is enforced by
reading a toggle. This is a case where the toggle lies. On an outbound workflow
it would select approved candidates and send email while appearing to be off.

**How to verify a workflow is really off.** Do not trust the toggle. Watch the
workflow's execution list and confirm **two consecutive missed schedule cycles**.
Absence of executions is the only trustworthy evidence.

**How to fix it.** Send an explicit deactivate even though the workflow already
reads inactive — that is what unregistered the trigger here. Do **not** toggle it
on first; that risks registering a second trigger. If the trigger persists,
restart the n8n container, which rebuilds the trigger registry from stored
state.

Note that the n8n activate endpoint requires a `versionId` in the request body.
A call without it fails with HTTP 400, which can look like a permissions problem
rather than a malformed request.

### Reading a missing Odoo record returns empty, not an error

**What happens.** Fetching a `crm.lead` by an ID that does not exist completes
**successfully** with an empty result. Confirmed with ID 999999: two scheduled
runs, both `success`.

**Why it matters.** A workflow whose record has been deleted or archived carries
on with empty data instead of failing. Downstream nodes then act on blanks, and
nothing in the execution log suggests a problem. This is the same failure shape
as an Odoo search returning no rows, which ends the run while still marking it
successful.

**Consequence for testing.** A missing record cannot be used to provoke the
error handler. Only a genuine outage will do it — stop the Odoo application
container, never its database.

**Consequence for design.** After any Odoo read whose result is then used, check
that a record actually came back. Do not infer it from the node succeeding.

### An Odoo update with an empty record ID reports success

**What happens.** An n8n Odoo `update` node whose record ID expression evaluates
to empty does not fail. It returns success, writes nothing, and the workflow
continues as though the write had landed.

**How it was found.** During B1 on 19 August the `Claim send key before SMTP`
node had its ID expression blanked by an earlier edit. The send key was never
written, the node reported success, and the email was sent anyway — removing
duplicate-send protection while every indicator said the run had worked.

**Why it matters.** This is the most dangerous member of the silent-success
family, because it sits on the outbound path. A blank ID means the guard writes
nothing and the send still happens.

**What to do.** After editing any Odoo write node, check **both** the target ID
expression and the field list. Do not assume a field-mapping edit preserved the
ID. Where a write is a safety control, verify the record afterwards rather than
trusting the node's success status.

### Editing workflows through the API while an editor tab is open

Changes made through the n8n REST API can be silently reverted by an open n8n
editor tab re-saving its own stale copy. Observed on 19 August: a verified fix
to the claim node was found undone later in the session.

Close editor tabs for a workflow before changing it through the API, and
re-read the workflow after saving to confirm the change is still there.

### Pre-activation checklist

Before activating any workflow, in this order:

1. Read the toggle state and confirm it shows inactive.
2. Watch the execution list for **two or more missed schedule cycles**.
3. Only then treat the workflow as off.

Step 2 is the one that matters. Step 1 on its own has already been wrong once.

## Send volume

- The system parameter `ggd_crm.daily_send_cap` (Settings > Technical >
  System Parameters) is the maximum number of send-key claims across all
  leads in any trailing 24 hours. The addon installs it at `20`; an upgrade
  never overwrites a value you set. `0` stops every send; a value that is not
  a whole number stops every send until corrected. Start low on a new domain
  and raise it as reputation builds.
- When the cap is reached, each further claim in a GGD-03 run fails with a
  ValidationError that names the cap, the error handler records it, and
  nothing is sent. That is expected, not a defect.

## Local security

- Both web ports bind to `127.0.0.1` only.
- PostgreSQL ports are not published.
- `.env` is excluded from Git.
- The Odoo master password is separate from the Odoo user login.
- The n8n owner password is separate from every other password.
- Never paste secrets into workflow code, notes, screenshots, or support messages.

## Public access later

Do not simply change the port binding to `0.0.0.0`.

For a VPS, add:

- HTTPS reverse proxy;
- firewall permitting only required ports;
- restricted SSH;
- automatic security updates;
- off-server backups;
- monitoring and restart alerts;
- a public webhook URL configured consistently in n8n.

For temporary local remote access, Cloudflare Tunnel is preferable to router port-forwarding, but it should be configured only after the local system and authentication have been verified.

## Migration outline

1. Stop n8n workflows and Odoo user activity.
2. Run `./scripts/backup.sh`.
3. Verify checksums and copy the backup off the computer.
4. Install the same Compose project on the target server.
5. Start only the database services.
6. Restore both SQL dumps.
7. Restore both application-data archives.
8. Start Odoo and n8n.
9. Set production URLs, HTTPS, secure cookies, and proxy mode.
10. Test without sending email.
11. Activate workflows one at a time.

Restoration is intentionally a supervised operation because it overwrites current state. Write and test a target-specific restore procedure before production migration.
