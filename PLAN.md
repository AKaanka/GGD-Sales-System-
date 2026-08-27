# Germany Growth Desk Sales System — Implementation Plan

## Final architecture

- **Odoo Community 19:** system of record for companies, contacts, opportunities, notes, stages, and activities.
- **n8n Community:** workflow orchestration, LLM calls, email monitoring, approval checks, and CRM updates.
- **Zoho Mail:** sends and receives GGD sales email from `kaan@germanygrowthdesk.com`.
- **LLM provider:** qualification, structured extraction, drafting, summarisation, and reply classification.
- **PostgreSQL:** separate persistent databases for Odoo and n8n.
- **Docker Compose:** portable local installation that can later move to a VPS.

## Non-negotiable controls

1. Odoo remains the authoritative record; the LLM never becomes the database.
2. Initial outreach is never sent without `Outreach approved` being true in Odoo.
3. `Do not contact` overrides every other workflow state.
4. LLM output is treated as a recommendation and stored with a confidence score.
5. Credentials stay in `.env` or the relevant application's encrypted credential store.
6. Local services bind only to `127.0.0.1`; public access is not enabled in phase one.
7. Real customer use requires an external backup and a reviewed lawful outreach process.

## Delivery phases

### Phase 1 — Local foundation

- Install Docker Desktop.
- Start Odoo, n8n, and their PostgreSQL databases.
- Create the `ggd` Odoo database without demo data.
- Install CRM and the included `GGD CRM` extension.
- Create the GGD pipeline and a test lead.

**Acceptance:** Odoo opens at `http://localhost:8069`, n8n at `http://localhost:5678`, and data survives a container restart.

### Phase 2 — CRM model

- Create pipeline stages matching the GGD commercial process.
- Add qualification, approval, contact-basis, reply-analysis, and AI-confidence fields.
- Add `Approve Outreach` and `Revoke Approval` controls.

**Acceptance:** a lead cannot enter an outbound workflow unless it is approved and not marked `Do not contact`.

### Phase 3 — Email connectivity

- Connect Zoho IMAP to n8n for incoming messages.
- Connect Zoho SMTP to n8n for approved outgoing messages.
- Store credentials only in n8n's encrypted credential store.
- Test with Kaan's own addresses before any prospect is contacted.

**Acceptance:** a test message is sent and its reply is received without exposing credentials in workflow JSON or logs.

### Phase 4 — Automation workflows

1. Lead qualification and structured market-fit analysis.
2. Personalised email draft and human approval gate.
3. Approved send, message-ID mapping, Odoo log, and next activity.
4. Reply classification, summary, suggested response, and CRM update.
5. Daily follow-up queue with suppression for negative replies and `Do not contact`.

**Acceptance:** all automatic updates are traceable in Odoo, and no unapproved email can leave the system.

### Phase 5 — QA and operating controls

- Test duplicate contacts, ambiguous replies, out-of-office messages, unsubscribe requests, failed LLM calls, and failed email delivery.
- Enable execution pruning and error notifications.
- Run and verify database/filestore backups.

**Acceptance:** each failure path stops safely and leaves a useful record for manual review.

### Phase 6 — VPS migration

- Move the same Compose project and restored backups to a small German VPS.
- Add HTTPS, restricted administration access, monitoring, and off-server backups.
- Keep the local installation as a test environment, not a second live CRM.

**Acceptance:** production is available 24/7 and can be restored from a tested backup.

## Build status

| Component | Status in this starter kit |
| --- | --- |
| Docker Compose foundation | Built |
| Persistent Odoo and n8n databases | Built |
| Local-only network exposure | Built |
| Secret-generation script | Built |
| GGD CRM Odoo extension | Built |
| CRM and automation specifications | Built |
| Backup script | Built |
| Beginner Codex operating guide | Built |
| GitHub repository instructions | Built |
| Automatic GitHub validation | Built |
| Zoho credentials | Requires Kaan's local setup |
| LLM credentials/provider selection | Requires Kaan's choice |
| Reproducible n8n workflow imports | Built for Workflows 1–5 and shared error handling; live import/acceptance pending |
| Public/VPS deployment | Deliberately deferred |

## Current implementation status

The repository contains addon version `19.0.1.6.0` and inactive, reproducible
imports for all five automation areas plus shared error handling. Offline
structure and decision tests pass. The current addon and imports are not
considered live-ready until Docker access is available, all Odoo tests pass,
the imports execute against the local Odoo/n8n versions, and the controlled
failure/send/reply paths are accepted.

See [docs/PROJECT-STATUS.md](docs/PROJECT-STATUS.md) for the verified work,
remaining checklist, and current time estimate.
