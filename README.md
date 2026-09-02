# GGD Sales System — Local Starter Kit

This package starts a private local sales stack for Germany Growth Desk:

- Odoo Community 19 with a GGD-specific CRM extension
- n8n Community with PostgreSQL
- a separate PostgreSQL database for Odoo
- persistent Docker volumes
- local-only ports
- secret generation, health checks, and backups

Read [PLAN.md](PLAN.md) before starting.

[NEXT-ACTIONS.txt](NEXT-ACTIONS.txt) is the single most current status file —
read it first. [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) carries the
fuller narrative and the time estimate.

As of 1 September, **all five gates are passed**, including the isolated
restore drill in [docs/RESTORE-DRILL.md](docs/RESTORE-DRILL.md).

**Compliance scope:** the product will be operated outside the EU, and
development is not constrained by GDPR or the German UWG §7 rule on marketing
email. [docs/COMPLIANCE-SCOPE.md](docs/COMPLIANCE-SCOPE.md) records that
decision (2 September 2026), lists what is out of scope, and explains why the
outbound gate stays anyway: every lead still needs a recorded contact basis and
a substantive note before outreach can be approved, because that is how list
provenance, opt-outs and sender reputation are kept, not because a law asks for
it. Every message sent so far has gone to a fictional `.invalid` fixture or to
Kaan's own address.

## Beginner route with Codex and GitHub

If you are not technical, start with
[docs/CODEX-GITHUB-GUIDE.md](docs/CODEX-GITHUB-GUIDE.md). It explains how to:

1. install Docker Desktop, GitHub Desktop, and ChatGPT desktop;
2. publish this project as a private GitHub repository;
3. open the folder in Codex;
4. start the system without exposing secrets;
5. build and test one Odoo/n8n stage at a time.

The repository includes `AGENTS.md`, which tells Codex to use plain language,
work in small stages, protect `.env`, and never send an unapproved email.

## 1. Prerequisites

- Docker Desktop with Docker Compose
- 8 GB RAM minimum; 16 GB recommended
- 20–40 GB free disk space
- macOS, Windows with WSL 2, or Linux

If Docker Desktop is already installed, confirm that both commands work:

```bash
docker --version
docker compose version
```

## 2. Create local secrets

Open Terminal in this project directory and run:

```bash
chmod +x scripts/*.sh
./scripts/setup-local.sh
```

The script creates a private `.env`, generates strong random secrets, validates the Compose file, downloads the images, and starts the services.

It does **not** connect Zoho, activate an LLM, expose the services publicly, or send email.

## 3. Create the Odoo database

1. Open `http://localhost:8069`.
2. Use the `ODOO_MASTER_PASSWORD` value from `.env` as the master password.
3. Database name: `ggd`.
4. Enter your administrator email and choose a separate login password.
5. Language: English.
6. Country: Germany.
7. Leave demo data disabled.
8. Create the database.

Never use the Odoo master password as your normal Odoo login password.

## 4. Install CRM and the GGD extension

1. Install the standard **CRM** application.
2. Open **Settings** and activate developer mode.
3. Open **Apps → Update Apps List**.
4. Remove the default `Apps` filter and search for `GGD CRM`.
5. Install **Germany Growth Desk CRM Controls**.
6. Follow [docs/ODOO-SETUP.md](docs/ODOO-SETUP.md) to create the pipeline.

The extension adds approval, compliance, qualification, reply-analysis, and LLM audit fields to opportunities.

## 5. Set up n8n

1. Open `http://localhost:5678`.
2. Create the local n8n owner account.
3. Do not enable public webhooks yet.
4. Add Zoho and LLM credentials only through n8n's **Credentials** interface.
5. Upgrade the GGD addon, then follow the
   [workflow import guide](workflows/README.md) to import Workflows 00–05.
6. Keep every imported workflow inactive until its manual test is verified in
   Odoo. Workflow 3 may be tested only with Kaan's explicit approval and a
   Kaan-owned recipient.

The imports use Odoo 19's JSON-2 API and a bearer token stored as an n8n HTTP
Header Auth credential. No Odoo password is embedded in workflow JSON.

## Daily commands

```bash
# Start or resume
docker compose up -d

# See status
docker compose ps

# Follow logs
docker compose logs -f --tail=100

# Stop without deleting data
docker compose stop

# Restart
docker compose restart
```

Do not run `docker compose down -v`; the `-v` option removes database volumes.

## Health check

```bash
./scripts/check-local.sh
```

## Project validation

Run this after Codex changes project files and before every GitHub push:

```bash
./scripts/validate-project.sh
```

GitHub runs the same validation automatically after each push and pull request.
It also checks all six workflow graphs and runs the offline reply-matching
decision suite.

## Backup

After the `ggd` Odoo database exists:

```bash
./scripts/backup.sh
```

Backups are written under `backups/`. Copy them to encrypted storage outside this computer. Keep the `.env` values in a password manager; the n8n encryption key is required to recover saved credentials.

## Safe email policy

- Research, classification, drafting, and record keeping may be automated.
- The first outbound version must require `Outreach approved` in Odoo.
- `Do not contact` must stop every send and follow-up path.
- Begin with emails to your own test addresses.
- A human approval is the authorisation record for one draft to one recipient; it does not vouch for the quality of the list the address came from. See [docs/COMPLIANCE-SCOPE.md](docs/COMPLIANCE-SCOPE.md).

## Moving to a VPS later

This project uses portable containers and named volumes. The migration process is:

1. stop local writes;
2. create a final backup;
3. copy this project and the backup to the VPS;
4. start the same major versions;
5. restore PostgreSQL and application data;
6. add HTTPS and restricted public access;
7. test before changing production DNS.

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for backup and update rules.
