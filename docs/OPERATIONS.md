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
