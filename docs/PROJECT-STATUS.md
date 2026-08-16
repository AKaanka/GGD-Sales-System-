# Project Status — 16 August 2026

## Plain-language summary

The private local sales system is running and the main CRM and automation
building blocks are in place. Odoo is the CRM record, n8n contains the
workflows, and both applications use persistent local databases. The system is
not yet ready for unattended production use: workflows remain manual or
inactive while the remaining failure tests, security review, and recovery test
are completed.

No real prospect was contacted during setup. Controlled email testing used the
owner's address, and reply analysis used fictional data.

## Completed and verified today

- Configured the fictional Odoo company, contact, opportunity, stages, GGD
  qualification fields, contact-basis controls, and approval controls.
- Verified approval, revocation, and `Do not contact` behaviour in Odoo.
- Updated the Odoo approval logic so revoking approval also clears the recorded
  approver and approval time.
- Created the local Odoo automation user and stored the Odoo credential in
  n8n's credential store.
- Connected the selected LLM through n8n's credential store and tested
  structured qualification and drafting with fictional data.
- Built the local n8n workflow set for qualification, draft preparation,
  approval-gated sending, reply analysis, follow-up review, and shared error
  handling. The workflow list was confirmed in n8n.
- Verified that the outbound gate blocks sending when approval is absent or
  revoked.
- Completed a controlled SMTP test to the owner's own mailbox. No prospect was
  contacted.
- Tested reply analysis with a fictional reply. Odoo received the category,
  summary, suggested action, confidence score, and internal audit note.
- Verified that invalid LLM output takes a manual-review path and does not send
  a response.
- Created a local backup under `backups/20260816T163337Z`.
- Ran `./scripts/validate-project.sh`: passed.
- Ran `./scripts/check-local.sh`: Odoo, n8n, and both databases were healthy.
- Confirmed `.env` remains ignored by Git and services remain bound locally.

## Remaining before routine local use

1. Copy the newest backup to encrypted storage outside this computer.
2. Test the reply-analysis unsubscribe path and confirm it immediately selects
   `Do not contact` in Odoo.
3. Test ambiguous reply matching, malformed LLM output, low confidence, an
   out-of-office reply, and a failed Odoo update.
4. Test the outbound workflow's duplicate-send protection and uncertain-send
   recovery without contacting a prospect.
5. Confirm the shared error workflow is assigned to every main workflow and
   stores only sanitized error details.
6. Review the Odoo automation user's minimum permissions and remove any access
   that is not required.
7. Test restoring a backup in an isolated local environment. Do not overwrite
   the working databases for this test.
8. Write and approve the lawful-contact procedure and production recipient
   checklist before importing or contacting real prospects.
9. Activate workflows one at a time only after their individual QA checklist
   passes. Keep outbound sending manually gated.

## Time estimate

For a beginner working carefully in the current local interface:

| Work | Estimated focused time |
| --- | ---: |
| Remaining workflow and failure-path QA | 4–7 hours |
| Permissions, error handling, and operating checklist | 2–3 hours |
| Off-computer backup and isolated restore test | 2–4 hours |
| Final local acceptance review | 1–2 hours |
| **Local system ready for controlled use** | **9–16 hours** |

A later production VPS migration, including HTTPS, firewall rules, monitoring,
off-server backups, restore testing, and final acceptance, is a separate
**8–14 hours**. Allow roughly **17–30 hours total** for controlled local
completion plus a careful first production deployment. Legal/compliance review
and any delays obtaining provider settings are not included.

## Next single action

Copy `backups/20260816T163337Z` to encrypted storage outside this computer.
After that, run the fictional unsubscribe test in Workflow 4. Do not activate
automatic sending yet.
