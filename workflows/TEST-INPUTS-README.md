# n8n Test Input Templates

**Status:** Ready for use in manual workflow testing. 18 August 2026.

Use these JSON files to manually test Workflow 3 and Workflow 5 without waiting for schedules or real candidates.

---

## How to Use

### Option 1: Manual Trigger Node (Easiest)

1. Open workflow in n8n
2. Click the first node (Schedule Trigger or similar)
3. Click "Test" or "Execute workflow"
4. If the trigger node has a test input area, paste the JSON from the appropriate file
5. Click "Execute"

### Option 2: Replace Trigger Output (Advanced)

If your trigger node doesn't support test input:

1. Open the trigger node settings
2. Note its output field name
3. In the next node's expression editor, reference the test data
4. Or create a "Code" node that outputs the test payload

---

## Workflow 3 Test Inputs

File: `test-inputs-workflow3.json`

### WS-B2: Basic Send

Use this to test successful send workflow with WS-F1 (approved opportunity).

```json
{
  "opportunity_id": 139,
  "name": "WS-F1: Approved Prospect",
  "email_from": "ws-f1@ggd-qa.invalid",
  "ggd_contact_basis": "consent",
  "ggd_contact_basis_note": "Opt-in via website form 2026-03-04, record ref WEB-1183.",
  "ggd_do_not_contact": false,
  "ggd_outreach_approved": true
}
```

**Expected result:**
- Email sent successfully
- ggd_last_send_key populated
- ggd_outreach_approved set to false (revoked)
- Chatter note created

---

### WS-B3: Idempotency Test

Use this after WS-B2 to verify re-running doesn't send again.

```json
{
  "opportunity_id": 139,
  "ggd_last_send_key": "139-send-20260818-124000",
  "ggd_do_not_contact": false,
  "ggd_outreach_approved": true
}
```

**Expected result:**
- Send key claim returns false
- No SMTP attempt
- No email sent

---

### WS-B4: Suppression Guard

Use this to test that WS-F2 (suppressed) doesn't send.

```json
{
  "opportunity_id": 140,
  "name": "WS-F2: Do Not Contact",
  "email_from": "ws-f2@ggd-qa.invalid",
  "ggd_contact_basis": "consent",
  "ggd_contact_basis_note": "Opt-in via website form 2026-03-04, record ref WEB-1183.",
  "ggd_do_not_contact": true,
  "ggd_outreach_approved": true
}
```

**Expected result:**
- Approval check fails with "ggd_do_not_contact is true"
- No email sent
- Review note created

---

### WS-B5: Basis-Missing Guard

Use this to test that missing contact basis prevents send.

```json
{
  "opportunity_id": 141,
  "name": "WS-F3: No Basis",
  "email_from": "ws-f3@ggd-qa.invalid",
  "ggd_contact_basis": null,
  "ggd_contact_basis_note": null,
  "ggd_do_not_contact": false,
  "ggd_outreach_approved": true
}
```

**Expected result:**
- Approval check fails with "ggd_contact_basis is empty"
- No email sent
- Review note created

---

## Workflow 5 Test Inputs

File: `test-inputs-workflow5.json`

### WS-B6: Stale Query (14-day-old)

Use this to test that 14-day-old opportunity appears in follow-up query.

```json
{
  "opportunity_id": 142,
  "name": "WS-F4: 14-Day-Old",
  "email_from": "ws-f4@ggd-qa.invalid",
  "ggd_last_message_date": "2026-08-04",
  "ggd_do_not_contact": false,
  "stage": "Qualified"
}
```

**Expected result:**
- Record included in query results
- Follow-up activity created
- Draft generated

---

### WS-B6: Control (3-day-old)

Use this to verify that 3-day-old opportunity is NOT in follow-up (not stale yet).

```json
{
  "opportunity_id": 143,
  "name": "WS-F5: 3-Day-Old",
  "email_from": "ws-f5@ggd-qa.invalid",
  "ggd_last_message_date": "2026-08-15",
  "ggd_do_not_contact": false,
  "stage": "Qualified"
}
```

**Expected result:**
- Record EXCLUDED from query
- No follow-up activity created

---

### WS-B8: Suppressed Record (skip)

Use this to test that suppressed records don't get follow-up.

```json
{
  "opportunity_id": 140,
  "name": "WS-F2: Suppressed",
  "email_from": "ws-f2@ggd-qa.invalid",
  "ggd_last_message_date": "2026-08-04",
  "ggd_do_not_contact": true,
  "stage": "Qualified"
}
```

**Expected result:**
- Record excluded from query
- No activity created

---

### WS-B8: Won Stage (skip)

Use this to test that won/lost records don't get follow-up.

```json
{
  "opportunity_id": 144,
  "name": "WS-F-Won: Already Won",
  "email_from": "ws-won@ggd-qa.invalid",
  "ggd_last_message_date": "2026-08-04",
  "ggd_do_not_contact": false,
  "stage": "Won"
}
```

**Expected result:**
- Record excluded from query
- No activity created

---

## Creating Custom Test Inputs

To test additional scenarios:

1. Copy one of the templates above
2. Modify the fields:
   - `opportunity_id`: Use actual Odoo record ID from your database
   - `email_from`: Test address (.invalid for safety)
   - `ggd_last_message_date`: Adjust date for stale/fresh testing
   - `stage`: Use actual stage names from your CRM
3. Run the workflow with your custom input
4. Verify results in Odoo

---

## Debugging with Test Inputs

If a workflow fails on a test input:

1. Check the error message in n8n execution detail
2. Enable verbose logging on problem nodes
3. Compare the test input fields against your workflow node's expected input shape
4. Use `console.log()` in Code nodes to debug variable values
5. Check Odoo logs for API call failures: `docker compose logs odoo --tail 50`

---

## Quick Checklist

- [ ] Test inputs created and documented
- [ ] Fixture IDs match your actual Odoo records
- [ ] Date fields use actual dates (adjust 14/3 day calculations for today)
- [ ] Email addresses are .invalid for safety
- [ ] Each test input has clear expected result
- [ ] Ready for use in manual workflow testing

