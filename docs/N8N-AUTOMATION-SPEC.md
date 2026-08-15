# n8n Automation Specification

This is the build specification for the first production-safe workflows. Build and test each workflow separately. Never put real credentials directly into node parameters or exported workflow JSON.

## Shared rules

Every outbound path must query the current Odoo record immediately before sending and require:

```text
ggd_outreach_approved == true
AND ggd_do_not_contact == false
AND ggd_contact_basis is not empty
```

If any condition fails, stop the workflow and add a review note. Do not rely on an earlier cached copy of the record.

Each LLM response must be parsed as structured JSON. If parsing fails or confidence is below the agreed threshold, route the item to manual review.

## Workflow 1 — Lead qualification

**Trigger:** manual execution first; later an Odoo stage/status poll.

**Nodes:**

1. Retrieve the Odoo opportunity and company/contact data.
2. Validate required source fields.
3. Fetch only approved public company-page content.
4. Send the minimum relevant content to the LLM.
5. Parse and validate the response.
6. Update the GGD qualification fields in Odoo.
7. Add a chatter note explaining which sources were used.
8. Leave the lead in `Qualified`; do not approve or send.

**Required LLM output:**

```json
{
  "industry": "string",
  "product_focus": "string",
  "fit_score": 0,
  "fit_summary": "string",
  "personalization_angle": "string",
  "recommended_buyer_roles": ["string"],
  "confidence": 0.0,
  "sources": ["https://example.com"]
}
```

Validation:

- `fit_score`: integer from 0 to 100
- `confidence`: number from 0 to 1
- all factual claims must have a source URL
- no invented contact names or email addresses

## Workflow 2 — Draft and approval queue

**Trigger:** opportunity enters `Draft Prepared` or a manual n8n test trigger.

**Nodes:**

1. Retrieve the opportunity and latest GGD qualification fields.
2. Confirm `ggd_do_not_contact == false`.
3. Generate one short draft in the appropriate language.
4. Store the draft as an Odoo note or activity for review.
5. Move to `Waiting for Approval`.
6. Stop.

The LLM must not set `ggd_outreach_approved`. Only the Odoo approval action used by an authorised human may set it.

## Workflow 3 — Approved send and record

**Trigger:** scheduled poll for approved opportunities; use a manual trigger during testing.

**Nodes:**

1. Retrieve the current Odoo opportunity.
2. Apply the shared approval rules.
3. Confirm recipient, subject, language, and final body.
4. Send through the saved Zoho SMTP credential.
5. Capture the SMTP message ID.
6. Write the message ID, sent time, recipient, subject, and body summary to Odoo.
7. Revoke or consume approval so the same message cannot be sent twice.
8. Schedule the next review activity.

**Idempotency:** store a unique send key such as `opportunity-id + draft-version`. Before sending, verify that the key has not already succeeded.

## Workflow 4 — Reply analysis

**Trigger:** Zoho IMAP Email Trigger.

**Nodes:**

1. Read sender, recipients, subject, `Message-ID`, `In-Reply-To`, and plain-text body.
2. Match `In-Reply-To` to the saved outbound message ID.
3. If no exact match exists, use sender email only to produce candidates; require manual review if more than one opportunity matches.
4. Remove quoted history and unnecessary signature content.
5. Send the minimum required body to the LLM.
6. Parse classification, summary, next action, and confidence.
7. Update the Odoo opportunity and add a chatter note.
8. For unsubscribe/stop requests, set `ggd_do_not_contact = true` immediately.
9. Create a response draft, but do not send it automatically in the initial release.

**Required LLM output:**

```json
{
  "category": "interested|meeting|information|objection|referral|not_interested|out_of_office|unsubscribe|unclear",
  "summary": "string",
  "suggested_next_action": "string",
  "suggested_follow_up_at": "ISO-8601 date-time or null",
  "response_draft": "string or null",
  "confidence": 0.0
}
```

## Workflow 5 — Daily follow-up queue

**Trigger:** schedule at 08:30 Europe/Berlin on working days.

1. Retrieve overdue Odoo activities and contacted opportunities without replies.
2. Exclude won, lost, and do-not-contact records.
3. Exclude any opportunity with an unresolved send or reply-analysis error.
4. Create a suggested follow-up draft.
5. Create an Odoo review activity.
6. Stop; do not send automatically in the initial release.

## Failure workflow

Create one shared n8n error workflow that records:

- workflow name and execution ID;
- opportunity ID, when available;
- failing node;
- error summary without secrets or full email bodies;
- whether a send may have occurred;
- manual recovery action.

If send outcome is uncertain, never retry automatically. Check Zoho Sent and the Odoo send key first.

## Credential checklist

- Odoo automation user credential
- Zoho IMAP credential
- Zoho SMTP credential
- LLM API credential

Use n8n's encrypted credential store. Keep `N8N_ENCRYPTION_KEY` in the `.env` file and a password manager. Losing that key can make restored credentials unreadable.

