# GGD n8n workflow imports

The six JSON files in this directory are the reproducible, inactive workflow
set. Import them into n8n in number order. They contain credential references
only; no passwords, API keys, or mailbox secrets are stored in Git.

## Before importing

1. Upgrade the `ggd_crm` addon in Odoo so version `19.0.1.8.0` is installed.
2. In the dedicated Odoo automation user's preferences, create an Odoo 19 API
   key.
3. In n8n, create an **HTTP Header Auth** credential named
   `Odoo JSON-2 bearer token`:
   - Header name: `Authorization`
   - Header value: `Bearer ` followed by the API key
4. Create or confirm the saved Anthropic, Zoho SMTP, and Zoho IMAP credentials
   in n8n. Do not paste their values into a workflow node.

## Import and connect

Import:

1. `GGD-00-shared-error-handler.json`
2. `GGD-01-lead-qualification.json`
3. `GGD-02-draft-approval-queue.json`
4. `GGD-03-approved-send.json`
5. `GGD-04-reply-and-bounce-intake.json`
6. `GGD-05-daily-follow-up.json`

After import:

1. Open every red credential node and select the matching saved credential.
2. In Workflow 3, replace `REPLACE_WITH_KAAN_TEST_SENDER` with the address
   belonging to the selected Zoho SMTP account.
3. Set Workflow 00 as the error workflow for Workflows 01–05.
4. Keep every workflow inactive while testing.
5. Upgrade the Odoo addon and run the Odoo tests before executing a workflow.

## Functional order

- Workflow 1 records sourced qualification and routes low-confidence results
  to review. It never approves outreach.
- Workflow 2 stores an immutable subject/body draft and stops for human review.
- A human reviews that exact draft and uses **Approve Outreach** in Odoo.
- Workflow 3 claims `opportunity-id:draft-version`, sends that exact reviewed
  draft, requires an SMTP Message-ID, and writes the complete audit to Odoo.
  If SMTP or final audit fails after the claim, it records an uncertain-send
  review. After checking Zoho Sent and confirming that nothing was sent, use
  **Release Failed Claim** in Odoo before retrying.
- Workflow 4 matches replies and bounces, suppresses hard bounces and
  unsubscribe requests, and stores response drafts without sending them.
- Workflow 5 creates one deduplicated manual follow-up activity for eligible
  sends that are at least seven days old and have no later reply.

## Test order

1. Run `./scripts/validate-project.sh`.
2. Run `./scripts/run-addon-tests.sh` and require all 108 tests to pass.
3. Manually test Workflows 1, 2, 4, and 5 with fictional `.invalid` records.
4. Test Workflow 3 only with a Kaan-owned recipient and explicit approval for
   that test send.
5. Activate one workflow at a time only after its manual result is verified in
   Odoo.

The Odoo calls use the Odoo 19 JSON-2 API at
`http://odoo:8069/json/2`. The database header is `ggd`, matching the local
starter-kit database name.
