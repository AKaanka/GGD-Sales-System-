# Instructions for Codex

This repository is the Germany Growth Desk sales-system starter. The owner is
not a software developer, so work in small, understandable stages.

## Start every task this way

1. Read `PLAN.md`, `README.md`, and the relevant file under `docs/`.
2. Explain the intended result in plain language before making a material change.
3. Inspect the current state; do not assume Docker, Odoo, or n8n is running.
4. Make the smallest safe change that completes the requested stage.
5. Run `./scripts/validate-project.sh` after code or configuration changes.
6. Summarise what changed, what was tested, and the next single action for Kaan.

## Safety rules

- Never read, print, commit, or overwrite `.env` unless Kaan explicitly asks for
  a specific local-secret operation. Refer to variable names, not secret values.
- Never put passwords, API keys, email credentials, tokens, or real prospect data
  into Git-tracked files, logs, screenshots, workflow exports, or chat messages.
- Never send an email or activate an n8n workflow that can send email without an
  explicit instruction from Kaan for that test.
- Use only Kaan's own test addresses until he explicitly approves a production
  recipient and the lead carries a recorded contact basis.
- The product is operated outside the EU. Do not add, keep, or scope work
  because of GDPR, UWG §7, or a lawyer's review; see
  `docs/COMPLIANCE-SCOPE.md`. The outbound gate stays for operational reasons.
- Preserve the outbound gate: `ggd_outreach_approved == true`,
  `ggd_do_not_contact == false`, and a non-empty contact basis.
- Do not make Odoo or n8n publicly accessible during the local phase.
- Do not run `docker compose down -v`, delete named volumes, delete backups, or
  perform another destructive operation without explaining the exact impact and
  receiving explicit confirmation.
- Do not change the pinned Odoo major version or database major versions during
  routine maintenance.

## Architecture boundaries

- Odoo is the authoritative CRM record.
- n8n orchestrates workflows and stores credentials in its credential store.
- Zoho is the mail provider; credentials are added manually in n8n.
- An LLM may classify, summarise, and draft. It must not approve outreach or act
  as the system of record.
- PostgreSQL data lives in Docker named volumes and is not committed to Git.

## Important files

- `PLAN.md`: architecture, controls, phases, and acceptance criteria.
- `README.md`: local installation and daily commands.
- `docs/CODEX-GITHUB-GUIDE.md`: beginner workflow for Codex and GitHub Desktop.
- `docs/ODOO-SETUP.md`: CRM configuration and control tests.
- `docs/N8N-AUTOMATION-SPEC.md`: workflow design and failure behaviour.
- `docs/OPERATIONS.md`: backups, updates, and VPS migration.
- `compose.yaml`: local Odoo, n8n, and database services.
- `scripts/validate-project.sh`: safe static validation.

## Definition of done

A task is complete only when the relevant validation passes, no secret was added
to Git, no unapproved email was sent, and Kaan receives one clear next action.
