# QA Investigation Log

This file preserves verified observations from the 16–17 August 2026 local QA
session. It is historical evidence, not the current testing procedure. Use
[QA-TEST-PACK.md](QA-TEST-PACK.md) for current instructions.

## Verified controls

- Odoo and n8n local health checks passed.
- Odoo and n8n bind to localhost; PostgreSQL ports are not published.
- The local `.env` is ignored by Git.
- The Odoo automation user had restricted CRM access and no Settings
  administrator role.
- All five main workflows referenced the shared error workflow.
- Main workflows were inactive and the shared error handler was active.

## Fictional fixtures created

| Fixture | Odoo ID | Purpose |
| --- | ---: | --- |
| F1 | 3 | approval and controlled-send history |
| F2 | 4 | ordinary safe tests |
| F3 | 5 | missing/invalid-data tests |
| F4 | 6 | unsubscribe and suppression tests |

All fixture addresses used the reserved `.invalid` domain. F1 and F4 became
suppressed during testing and must not be reset merely to make another test
convenient.

## Reply-matching investigation

- The original Workflow 4 was not broken. Its manual test path obtained the
  opportunity ID from the fictional fixture.
- Earlier statements that its code node did not exist or that the original
  workflow was broken were incorrect and are retracted.
- WIP copy 04b was abandoned after an accidental edit removed required logic.
- WIP copy 04c was rebuilt to explore production-safe matching:
  sender-email search first, followed by outbound-message/thread fallback.
- At the stopping point, sender search and fallback retrieval were present.
  Match-decision logic and the final suppression guard still required work.
- IMAP triggering remained disabled.

## Reply-test evidence

- A single-match unsubscribe test set do-not-contact, revoked approval, and
  cleared outreach metadata.
- An ambiguous sender match followed the manual-review path without a CRM write
  or LLM call.
- A polite stop request was classified as an unsubscribe.
- A reply against a suppressed record preserved suppression, but the generated
  suggested action could still recommend an unsafe follow-up. This is a known
  defect and is now acceptance test A9.

## Outbound-test evidence

- A controlled owner-mailbox test demonstrated the approval gate.
- After a successful controlled send, approval consumption and audit recording
  were exercised.
- Revoking approval prevented the email branch from running.

These observations do not authorize any future send. Every email test still
requires explicit approval for that specific test and must use only Kaan's own
mailbox.

## Filestore incident

An older backup used Odoo's default
`.local/share/Odoo/filestore/<db>` layout while the current configuration uses
`/var/lib/odoo/filestore/<db>`. The split caused asset
`FileNotFoundError` failures and a blank-looking UI. The active files were
consolidated into the configured `data_dir` path. The safe restore context is
documented in [OPERATIONS.md](OPERATIONS.md).

## Other observations

- Workflow 1 temporarily carried a `My` prefix; naming should be normalized
  during final workflow cleanup.
- An orphan standalone n8n container was observed outside the intended Compose
  stack. Removing it is a separate destructive operation and requires Kaan to
  confirm the exact target first.
