# GGD Sales System — Current Acceptance Tests

Status: **in progress**. This pack addresses hardening items 2–6 in
[PROJECT-STATUS.md](PROJECT-STATUS.md); those items remain open until every
required result below is recorded as passing.

Historical findings and retracted hypotheses are kept separately in
[QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md). They are evidence, not
instructions.

## Safety rules

1. Run one test at a time. Stop on the first unexpected result.
2. Keep production-capable workflows inactive while testing manually.
3. Use fictional records and `.invalid` addresses only.
4. Never send to a prospect. Any email-send test requires Kaan's explicit
   approval immediately before that test and must use only Kaan's own mailbox.
5. Create a fresh backup before restore, failure-injection, or email tests.
6. Do not display or copy credential values into notes, screenshots, or Git.
7. Run `./scripts/validate-project.sh` after tracked configuration changes.

## Baseline already verified

| Control | Current evidence |
| --- | --- |
| Local services | Odoo and n8n health checks passed |
| Network exposure | Odoo and n8n bind to `127.0.0.1`; database ports are unpublished |
| Secrets | Local `.env` is ignored by Git |
| Odoo automation user | Restricted CRM access; no Settings administrator role |
| Error workflow | All five main workflows reference the shared error handler |
| Workflow activation | Main workflows inactive; shared error handler active |
| Outbound gate | Requires approval, no suppression, and a non-empty contact basis |

The sender-email fallback was exercised in a work-in-progress copy. It is not
approved as a replacement for the original reply workflow until the final
matching and suppression tests pass. IMAP remains disabled.

## Fictional fixtures

| Fixture | Odoo ID | Purpose | Permanent state |
| --- | ---: | --- | --- |
| F1 | 3 | approved-send and approval-consumption history | Suppressed after test; do not clear |
| F2 | 4 | ordinary safe test record | Reusable |
| F3 | 5 | missing/invalid-data tests | Reusable |
| F4 | 6 | unsubscribe and suppression tests | Suppressed; do not clear |

Do not reset F1 or F4 to an approved, contactable state. Create a new fictional
fixture whenever a test needs fresh approval.

## A. Reply workflow acceptance

### A1 — Single sender match

- Input: one fictional reply whose normalized sender matches exactly one
  fictional opportunity.
- Expected: the correct opportunity is selected; no other record is changed.
- Current status: passed on an earlier WIP copy; rerun on the final workflow.

### A2 — Ambiguous sender match

- Input: two opportunities with the same normalized sender.
- Expected: manual-review path; no CRM update and no LLM call.
- Current status: passed on an earlier WIP copy; rerun on the final workflow.

### A3 — No sender match and valid thread fallback

- Input: no sender match, with a valid known outbound message/thread ID.
- Expected: one opportunity selected through the thread fallback.
- Current status: not run.

### A4 — No sender or thread match

- Input: no sender match and no valid fallback.
- Expected: manual-review/error note only; no CRM reply fields updated.
- Current status: passed on an earlier WIP copy; rerun on the final workflow.

### A5 — Malformed LLM JSON

- Inject malformed model output in a test-only copy.
- Expected: validation fails; no CRM reply fields updated; no response sent.
- Current status: not run on the final workflow.

### A6 — Low confidence

- Inject valid output below the configured confidence threshold.
- Expected: manual review; no unattended action.
- Current status: not run.

### A7 — Out-of-range confidence

- Inject confidence below 0 or above 1.
- Expected: validation fails and the invalid-output audit note is recorded.
- Current status: not run.

### A8 — Odoo temporarily unavailable

- Create a fresh backup and record the exact Compose project and service names.
- Stop only the Odoo application container; do not stop or delete its database.
- Execute the test workflow and then restart Odoo.
- Expected: sanitized error handling; no secrets; no duplicate CRM write after
  recovery.
- Current status: not run.

### A9 — Reply to a suppressed lead

- Use F4 without clearing suppression.
- Expected: `ggd_do_not_contact` stays true, approval stays false, and the
  suggested action never recommends sending or following up.
- Current status: partial. Suppression was preserved, but an unsafe suggested
  action was generated. This is a known defect and must pass before sign-off.

## B. Outbound workflow acceptance

Use a newly created fictional fixture for B1–B5. Do not reuse F1 or F4.
Before any actual email test, Kaan must explicitly approve that single test and
the recipient must be Kaan's own mailbox.

### B1 — Duplicate-send prevention

- Execute the same approved item twice.
- Expected: one email at most; the second execution is blocked and audited.
- Status: not run formally.

### B2 — Approval consumed after send

- Expected after one successful controlled send: approval becomes false and
  the send/message audit reference is stored.
- Status: observed previously; rerun formally with a fresh fixture.

### B3 — Suppression gate

- Set `ggd_do_not_contact = true`.
- Expected: send node is not reached.
- Status: gate behavior observed; formal recorded run pending.

### B4 — Missing contact basis

- Remove the contact basis from an otherwise approved fictional record.
- Expected: send node is not reached and the reason is recorded.
- Status: not run formally.

### B5 — SMTP failure

- Use a controlled local or dedicated SMTP test service that cannot deliver to
  real recipients. Do not deliberately damage the normal Zoho credential.
- Expected: sanitized error handler, no approval consumption, and no duplicate
  send during retry.
- Status: test method not yet implemented.

## C. Error handling and least privilege

### C1 — Shared error workflow

- For each main workflow, cause one safe test-only failure.
- Expected: the shared handler records a sanitized note and never includes
  credential values.
- Status: handler assignment passed; deliberate failure test pending per
  workflow.

### C2 — Sanitized audit notes

- Review all generated error notes.
- Expected: node/workflow context is useful, but passwords, API keys, SMTP
  credentials, tokens, and full sensitive payloads are absent.
- Status: partial; complete after C1.

### C3 — Odoo automation-user denial

- Attempt one read/write outside the required CRM scope using the automation
  credential.
- Expected: access denied while required CRM workflow actions still succeed.
- Status: group membership inspected; interactive denial test pending.

## D. Backup and restore acceptance

1. Create a new backup and copy it to encrypted storage outside this computer.
2. Prepare an isolated Compose project with explicitly different project,
   container, network, and volume names.
3. Restore the matching Odoo database/filestore pair and the matching n8n
   database/data pair.
4. Confirm Odoo assets load, the fictional CRM records exist, n8n opens, and
   workflows/credentials are present without sending email.
5. Record the restore duration and result.
6. Delete the isolated test environment only after Kaan reviews the exact
   container and volume names and explicitly confirms deletion.

Status: backup creation passed; isolated restore drill pending.

## Sign-off

Production outreach remains blocked until:

- every required test above passes;
- the suppressed-reply defect in A9 is fixed;
- the final Workflow 4 reply-matching design passes A1–A4;
- the lawful-contact procedure receives qualified legal review;
- a final backup and isolated restore drill pass; and
- Kaan explicitly approves production activation.
