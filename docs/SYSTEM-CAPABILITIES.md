# GGD Sales System — Functional Capabilities

Status date: 21 August 2026.

This document describes the current repository build. “Implemented” means the
function exists in the Odoo addon and/or an inactive n8n import. It does not
mean the current local containers have been upgraded and acceptance-tested.
Live verification is still pending.

## End-to-end flow

```text
New Odoo opportunity
  → Workflow 1: sourced qualification
  → Workflow 2: versioned subject/body draft
  → human reviews that exact draft and approves in Odoo
  → Workflow 3: claim version, send exact draft, record SMTP audit
  → Workflow 4: match reply or bounce and update Odoo
  → Workflow 5: queue a manual follow-up after seven days with no reply
```

Odoo is the system of record. The LLM can qualify, classify, summarize, and
draft; it cannot approve outreach or send a follow-up by itself.

## Odoo CRM functions

Implemented in addon version `19.0.1.8.0`:

- qualification fields, source URL, fit score, fit summary, personalization
  angle, recommended buyer roles, confidence, and review status;
- contact-basis evidence, human approval metadata, and Do-not-contact control;
- reviewed draft subject/body, immutable draft version, approved version, and
  draft state;
- deterministic send claim using `opportunity-id:draft-version`;
- SMTP confirmation time, Message-ID, recipient, subject, body summary, and
  confirmed send key;
- reply category, summary, next action, response draft, follow-up time, reply
  Message-ID, and ISO-8601 received timestamps;
- accepted/bounced delivery state and hard-bounce suppression;
- separate qualification, reply, delivery, and workflow-error review flags;
- one atomic, deduplicated manual follow-up activity per confirmed send.

Changing a reviewed draft revokes any older approval. Finalizing a send without
all four SMTP audit values is refused. A bounce is accepted only when it exactly
matches a confirmed outbound Message-ID.

## Workflow 1 — Lead qualification

Implemented as inactive import `GGD-01-lead-qualification.json`.

- Selects active, pending opportunities with either the visible GGD research
  source URL or the standard company website.
- Fetches and minimizes the public page content.
- Requires structured industry, product focus, fit score, summary,
  personalization angle, buyer roles, confidence, and sources.
- Validates score/confidence/source shape before updating Odoo.
- Routes confidence below 0.70 to human review.
- Never grants outreach approval.

## Workflow 2 — Draft and approval queue

Implemented as inactive import `GGD-02-draft-approval-queue.json`.

- Selects qualified, unsuppressed opportunities without a draft.
- Generates one short subject/body draft from stored qualification data.
- Validates draft length and stores a new immutable version in Odoo.
- Stops for human review.
- Never sets `ggd_outreach_approved` and never sends email.

## Workflow 3 — Approved reviewed-draft send

Implemented as inactive import `GGD-03-approved-send.json`.

- Polls every 15 minutes when activated and selects at most ten approved
  records.
- Rechecks approval, suppression, contact basis, recipient, draft status, and
  equality of current/approved draft versions.
- Claims the deterministic key in Odoo before SMTP.
- Sends the exact stored subject/body through the selected Zoho credential.
- Requires SMTP to return a Message-ID.
- Finalizes the full audit in Odoo and consumes approval.
- Does not generate or alter the email after approval.
- Records SMTP/final-audit failures as uncertain sends. A human must inspect
  Zoho Sent and explicitly release a known-failed claim before it can retry.

This is the only send-capable workflow. It remains inactive and its sender is a
visible placeholder until Kaan authorizes a test to his own address.

## Workflow 4 — Reply and bounce intake

Implemented as inactive import `GGD-04-reply-and-bounce-intake.json`.

- Reads Zoho IMAP messages, normalizes headers, strips quoted history and
  minimizes the body.
- Matches exact `In-Reply-To`/outbound Message-ID first, then sender email.
- Continues automatically only when exactly one Odoo opportunity matches.
- Creates a deduplicated Odoo review record/activity for unmatched or
  ambiguous mail instead of dropping it.
- Requires an exact outbound Message-ID for bounces.
- Records hard/soft bounce state; hard bounces set Do not contact.
- Classifies ordinary replies into the defined categories, stores a summary,
  suggested next action/time, confidence, and a response draft.
- Immediately suppresses unsubscribe/stop requests.
- Does not store an outbound response draft for a suppressed contact and never
  sends a response draft.

IMAP does not mark the message read before durable handling; the export uses
persistent message tracking for retry-safe intake.

## Workflow 5 — Daily follow-up queue

Implemented as inactive import `GGD-05-daily-follow-up.json`.

- Runs at 08:30 Europe/Berlin on weekdays when activated.
- Selects active, non-won, unsuppressed records with an SMTP-confirmed send at
  least seven days old.
- Excludes records with a later reply or unresolved automation review.
- Generates a follow-up draft and calls the locked Odoo queue method.
- Creates one To-Do activity per confirmed send, even if two scheduler runs
  overlap.
- Never sends the follow-up automatically.

## Shared error workflow

Implemented as inactive import `GGD-00-shared-error-handler.json`.

- Records workflow name, execution ID, failing node, concise sanitized summary,
  opportunity ID when recoverable, and whether SMTP may already have run.
- Adds an Odoo review item when the opportunity can be identified.
- Instructs the operator to inspect Zoho Sent and the Odoo claim before any
  retry after an uncertain send.

The imported error workflow must be selected in Workflows 1–5 settings because
n8n assigns local workflow IDs only after import.

## Current verification boundary

Verified offline:

- project/static validation;
- six JSON exports parse and all connection names/targets exist;
- Workflow 3 graph orders claim → SMTP → finalize;
- Workflows 2, 4, and 5 contain no email-send node;
- current workflow export/decision tests: 14 passed, 0 failed;
- legacy reply-matcher regression tests: 19 passed, 0 failed (separate from the
  current export implementation).

Not yet verified on the current build:

- addon upgrade and all 102 Odoo tests;
- import compatibility and execution in the local n8n version;
- live Odoo JSON-2 credential binding;
- live Anthropic, IMAP, and SMTP behavior;
- controlled end-to-end send/reply/bounce recovery.

See [PROJECT-STATUS.md](PROJECT-STATUS.md) and
[the workflow import guide](../workflows/README.md) for the remaining steps.
