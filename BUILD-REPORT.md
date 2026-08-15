# Build Report

## Completed

- Local-only Docker Compose topology for Odoo 19, n8n, and two PostgreSQL databases
- Persistent named volumes and database health dependencies
- Secret-generation and startup script
- Local health-check script
- Odoo/n8n database and application-data backup script
- Odoo 19 `ggd_crm` extension with:
  - company qualification fields;
  - fit score and confidence validation;
  - contact-basis record;
  - human outreach approval action;
  - do-not-contact enforcement;
  - reply classification and message-ID fields;
  - approval/revocation chatter records
- GGD pipeline and data-entry specification
- Five n8n workflow specifications and safe failure behavior
- Operations, backup, update, and VPS migration guidance
- Beginner Codex and GitHub Desktop guide with copy-and-paste prompts
- Repository-level Codex safety instructions in `AGENTS.md`
- Local and GitHub Actions validation through `scripts/validate-project.sh`

## Validation performed

- Shell syntax validation for all scripts
- Python AST parsing for the Odoo addon
- XML parsing for the inherited Odoo view
- YAML parsing and expected-service validation for `compose.yaml`
- Confirmed the inherited Odoo 19 CRM form contains the referenced form ID, header, and notebook anchors
- Checked that databases are not exposed and web ports bind to `127.0.0.1`
- Confirmed `.env`, backups, and shared runtime files are excluded from Git
- Confirmed the official Odoo image receives its master password and database
  filter as supported Odoo command-line arguments
- Pinned the starter images to Odoo `19.0-20260810` and n8n `2.34.6` for a
  reproducible first installation

## Validation requiring the target computer

Docker is not installed in the build environment used to assemble this package, so the containers could not be launched here. The next validation must run on Kaan's computer:

1. `docker compose config --quiet`
2. `./scripts/setup-local.sh`
3. `./scripts/check-local.sh`
4. create the Odoo database and install CRM plus `GGD CRM`
5. execute the six control tests in `docs/ODOO-SETUP.md`

No Zoho credential, LLM credential, real prospect data, or outbound email is included in this package.
