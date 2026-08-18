# Work-Selection Layer Implementation Guide

**Status:** Implementation guide for n8n builders. 18 August 2026.

This guide walks through building the automatic scheduling and candidate-selection workflows in n8n, using the test specifications in [WORK-SELECTION-TESTS.md](WORK-SELECTION-TESTS.md).

## Prerequisites

- n8n is running on http://localhost:5678
- Odoo is running on http://localhost:8069
- Zoho SMTP credentials are saved in n8n's credential store
- Odoo automation-user credential exists in n8n
- GGD 04 (live workflow) is present and inactive
- GGD 99 (error handler) is active and working (after C0 proof settles)

---

## Workflow 3 — Approved Send (Scheduled Outbound)

This workflow finds approved opportunities and sends them automatically every 15 minutes.

### 3.1 Create the trigger

**Node:** Interval trigger (Schedule)

Configuration:
- **Type:** Interval
- **Interval:** every 15 minutes
- **Timezone:** Europe/Berlin

Purpose: Run automatically every 15 minutes. The interval avoids SMTP load pressure from running too frequently.

---

### 3.2 Query approved candidates

**Node:** Odoo API call (HTTP request or native Odoo node if available)

Configuration:

```xml
<!-- XML-RPC call to crm.lead.search_read() -->
<!-- Use native Odoo node if n8n has one, otherwise HTTP POST to Odoo -->

<methodCall>
  <methodName>execute_kw</methodName>
  <params>
    <param><value><string>ggd</string></value></param>
    <param><value><int>2</int></value></param>
    <!-- automation user ID, from credential -->
    <param><value><string>PASSWORD</string></value></param>
    <!-- from credential -->
    <param><value><string>crm.lead</string></value></param>
    <param><value><string>search_read</string></value></param>
    <param><value>
      <array><data>
        <value><array><data>
          <value><array><data>
            <value><string>ggd_outreach_approved</string></value>
            <value><string>=</string></value>
            <value><boolean>1</boolean></value>
          </data></array></value>
          <value><array><data>
            <value><string>ggd_do_not_contact</string></value>
            <value><string>=</string></value>
            <value><boolean>0</boolean></value>
          </data></array></value>
          <value><array><data>
            <value><string>ggd_contact_basis</string></value>
            <value><string>!=</string></value>
            <value><string></string></value>
          </data></array></value>
          <value><array><data>
            <value><string>active</string></value>
            <value><string>=</string></value>
            <value><boolean>1</boolean></value>
          </data></array></value>
        </data></array>
      </data></array>
    </param>
    <param><value>
      <array><data>
        <value><string>id</string></value>
        <value><string>email_from</string></value>
        <value><string>partner_id</string></value>
        <value><string>name</string></value>
        <value><string>ggd_contact_basis</string></value>
        <value><string>ggd_contact_basis_note</string></value>
        <value><string>ggd_do_not_contact</string></value>
        <value><string>ggd_outreach_approved</string></value>
      </data></array>
    </param>
    <param><value>
      <array><data>
        <value><array><data>
          <value><string>ggd_outreach_approval_date</string></value>
          <value><string>asc</string></value>
        </data></array></value>
      </data></array>
    </param>
    <param><value><int>10</int></value></param>
    <!-- Limit: process up to 10 per run -->
    <param><value><int>0</int></value></param>
  </params>
</methodCall>
```

**Output:** Array of opportunity objects with id, email_from, name, approval state

---

### 3.3 Handle empty candidate set

**Node:** "If" condition or Always Output Data node

Configuration:
- **Condition:** If results array is empty
- **True path:** Add a note to Odoo chatter or log (optional, workflow succeeds)
- **False path:** Continue to loop

Purpose: Prevent workflow failure when no approved opportunities are waiting. Provides graceful handling of "nothing to do" case.

---

### 3.4 Loop through each record

**Node:** For Each loop (if n8n has one) or iterate manually

Configuration:
- **Input:** Previous node's results array
- **Iterations:** Process one record at a time

---

### 3.5 Per-record: Apply approval rules

**Node:** Code block (JavaScript or Python)

Logic:

```javascript
// Input: current record from loop
const record = $json.json;

const violations = [];

if (record.ggd_do_not_contact) {
  violations.push("ggd_do_not_contact is true");
}
if (!record.ggd_outreach_approved) {
  violations.push("ggd_outreach_approved is false");
}
if (!record.ggd_contact_basis) {
  violations.push("ggd_contact_basis is empty");
}
if (!record.ggd_contact_basis_note || record.ggd_contact_basis_note.length < 20) {
  violations.push("ggd_contact_basis_note is empty or too short");
}

// Store violations for routing
$json.approvalViolations = violations;
$json.canSend = violations.length === 0;
```

**Output:** Modified record with `canSend` and `violations` fields

---

### 3.6 Branch: denied → error/review

**Node:** "If" statement

Configuration:
- **Condition:** If `canSend` is false
- **True path:** Continue to send
- **False path:** Create review note in Odoo

For the false path:

**Sub-node:** Odoo API call to create a mail.message (chatter note)

```javascript
// Create note explaining rejection
"GGD outreach not sent: " + violations.join("; ") + " — requires manual review or correction."
```

Then continue to next record in loop.

---

### 3.7 Claim send key

**Node:** Odoo API call (execute method)

Configuration:

```xml
<methodCall>
  <methodName>execute_kw</methodName>
  <params>
    <!-- database, user_id, password from credential -->
    <param><value><string>crm.lead</string></value></param>
    <param><value><string>ggd_claim_send_key</string></value></param>
    <param><value>
      <array><data>
        <value><int>RECORD_ID</int></value>
      </data></array>
    </param>
    <param><value>
      <array><data>
        <!-- send_key: opportunity_id + draft_version -->
        <!-- example: "123-draft-v1" for record 123, draft version 1 -->
        <value><string>{{ record.id }}-send-{{ now().format('YYYYMMDD-HHmmss') }}</string></value>
      </data></array>
    </param>
  </params>
</methodCall>
```

**Output:** Boolean (true = key claimed, false = already sent)

---

### 3.8 Branch: key already sent → stop

**Node:** "If" statement

Configuration:
- **Condition:** If claim returned false
- **True path:** Log and continue to next record (send already happened)
- **False path:** Continue to SMTP

---

### 3.9 Generate draft

**Node:** LLM call (Anthropic Chat Model)

Configuration:
- **Input:** Previous record data
- **Prompt:** Generate a short, personalized outreach email based on qualification data
- **Output:** Draft subject and body

---

### 3.10 Send via SMTP

**Node:** Send Email

Configuration:
- **From:** Your Zoho-authenticated sender address
- **To:** `record.email_from`
- **Subject:** From draft
- **Body:** From draft
- **Credential:** Zoho SMTP

**Important:** This node runs ONLY if the send key was successfully claimed (step 3.8 true branch).

---

### 3.11 Finalize send

**Node:** Odoo API call (execute method)

Configuration:

```xml
<methodCall>
  <methodName>execute_kw</methodName>
  <params>
    <!-- database, user_id, password -->
    <param><value><string>crm.lead</string></value></param>
    <param><value><string>ggd_finalize_send</string></value></param>
    <param><value>
      <array><data>
        <value><int>RECORD_ID</int></value>
      </data></array>
    </param>
  </params>
</methodCall>
```

Purpose:
- Updates ggd_last_message_date
- Revokes ggd_outreach_approved
- Adds chatter note confirming send

**Important:** Only runs if SMTP succeeded (success path from 3.10).

---

### 3.12 Error handler reference

**Settings:**
- **Error workflow:** GGD 99 (shared error handler)
- **Retry policy:** No auto-retry (failure is not recoverable in send path)

All nodes should reference the error handler so failures are logged sanitized and traceable.

---

## Workflow 5 — Daily Follow-up Queue

This workflow finds stale opportunities and creates follow-up activities.

### 5.1 Create the schedule trigger

**Node:** Cron schedule

Configuration:
- **Cron expression:** `0 8 * * 1-5` (08:30 Monday–Friday)
- **Timezone:** Europe/Berlin

Or use the UI to set: 08:30 daily, skip Saturday/Sunday.

---

### 5.2 Query stale opportunities

**Node:** Odoo API call

Configuration:

```xml
<!-- Search for opportunities not contacted in 7+ days -->
<methodCall>
  <methodName>execute_kw</methodName>
  <params>
    <param><value><string>ggd</string></value></param>
    <param><value><int>USER_ID</int></value></param>
    <param><value><string>PASSWORD</string></value></param>
    <param><value><string>crm.lead</string></value></param>
    <param><value><string>search_read</string></value></param>
    <param><value>
      <array><data>
        <value><array><data>
          <value><string>active</string></value>
          <value><string>=</string></value>
          <value><boolean>1</boolean></value>
        </data></array></value>
        <value><array><data>
          <value><string>ggd_do_not_contact</string></value>
          <value><string>=</string></value>
          <value><boolean>0</boolean></value>
        </data></array></value>
        <value><array><data>
          <value><string>stage_id.name</string></value>
          <value><string>not in</string></value>
          <value><array><data>
            <value><string>Won</string></value>
            <value><string>Lost</string></value>
          </data></array></value>
        </data></array></value>
        <value><array><data>
          <value><string>ggd_last_message_date</string></value>
          <value><string>&lt;</string></value>
          <!-- today - 7 days, using Odoo datetime -->
          <value>{{ now().add(-7, 'days').format('YYYY-MM-DD') }}</value>
        </data></array></value>
      </data></array>
    </param>
    <param><value>
      <array><data>
        <value><string>id</string></value>
        <value><string>name</string></value>
        <value><string>email_from</string></value>
        <value><string>ggd_last_message_date</string></value>
        <value><string>stage_id</string></value>
      </data></array>
    </param>
    <param><value>
      <array><data>
        <value><array><data>
          <value><string>ggd_last_message_date</string></value>
          <value><string>asc</string></value>
        </data></array></value>
      </data></array>
    </param>
    <param><value><int>5</int></value></param>
    <!-- Limit to 5 follow-ups per day -->
  </params>
</methodCall>
```

**Output:** Array of stale opportunity objects

---

### 5.3 Always Output Data

Same as Workflow 3.3 — handle empty result gracefully.

---

### 5.4 Loop through records

Same as Workflow 3.4.

---

### 5.5 Generate follow-up draft

**Node:** LLM call

Configuration:
- **Input:** Record's prior messages, stage, last action
- **Prompt:** Generate a personalized follow-up email acknowledging the prior conversation and moving toward next steps
- **Output:** Draft subject and body

---

### 5.6 Create follow-up activity

**Node:** Odoo API call

Configuration:

```xml
<methodCall>
  <methodName>execute_kw</methodName>
  <params>
    <param><value><string>ggd</string></value></param>
    <param><value><int>USER_ID</int></value></param>
    <param><value><string>PASSWORD</string></value></param>
    <param><value><string>mail.activity</string></value></param>
    <param><value><string>create</string></value></param>
    <param><value>
      <array><data>
        <value><array><data>
          <value><string>activity_type_id</string></value>
          <value><int>4</int></value>
          <!-- "Follow-up" activity type; adjust ID if different -->
        </data></array>
        <value><array><data>
          <value><string>res_model_id</string></value>
          <value><int>86</int></value>
          <!-- crm.lead model ID; adjust if different -->
        </data></array>
        <value><array><data>
          <value><string>res_id</string></value>
          <value><int>RECORD_ID</int></value>
        </data></array>
        <value><array><data>
          <value><string>user_id</string></value>
          <value><int>2</int></value>
          <!-- Your assigned user ID -->
        </data></array>
        <value><array><data>
          <value><string>date_deadline</string></value>
          <value><string>{{ now().add(1, 'days').format('YYYY-MM-DD') }}</string></value>
          <!-- Due tomorrow -->
        </data></array>
        <value><array><data>
          <value><string>summary</string></value>
          <value><string>Follow-up on {{ record.name }}</string></value>
        </data></array>
        <value><array><data>
          <value><string>note</string></value>
          <value><string>DRAFT:\n{{ draft_subject }}\n\n{{ draft_body }}</string></value>
        </data></array>
      </data></array>
    </param>
  </params>
</methodCall>
```

Purpose: Creates a visible activity in Odoo with the draft text. Human will review and decide whether to send.

---

### 5.7 Add chatter note

**Node:** Odoo API call (create mail.message)

Configuration:

```javascript
// Log that follow-up was queued
"GGD: Follow-up draft created by automated workflow. Review the follow-up activity. Do not send automatically in this release."
```

---

### 5.8 Error handler reference

Same as Workflow 3.12.

---

## Common Node Configuration Patterns

### Always Output Data node

Used in both workflows to prevent silent stalls when query returns no results.

**Configuration:**
- **Execute even if previous node returns empty:** true
- **Output mode:** Use 0 if empty (or equivalent in your n8n version)

This ensures the workflow completes successfully even if there are no candidates to process.

---

### Error handler routing

Every workflow must reference the shared error handler (`GGD 99`).

**Steps:**
1. Open workflow settings
2. Find "Error workflow" or "On error" section
3. Select `GGD 99 - Shared Error Handler`
4. Ensure all nodes have **retryOnFail: false** (no auto-retry; let the error handler log it)

---

## Testing and Validation Checklist

After building each workflow:

1. [ ] **Manual trigger test:** Run workflow manually with test data
   - Confirm candidates are selected
   - Confirm approval rules are applied
   - Confirm chatter notes are created

2. [ ] **Schedule trigger test:** Wait for schedule and confirm auto-execution
   - Workflow 3: Check every 15 minutes
   - Workflow 5: Check at 08:30 Berlin time

3. [ ] **Idempotency test:** Re-run immediately and confirm no duplicates
   - Workflow 3: No double-send if run twice
   - Workflow 5: No duplicate activity if run twice

4. [ ] **Error handling:** Break something (wrong SMTP credentials, stop Odoo) and confirm error handler fires
   - Check GGD 99 has a new execution
   - Verify no secrets in the error log

5. [ ] **Suppress-contact guard:** Create suppressed record and confirm it's skipped
   - No send for suppressed records
   - Chatter note explains why

6. [ ] **Empty candidate set:** Run when no records match query
   - Workflow completes without error
   - No false positives sent

---

## Deployment order

1. Build and test Workflow 3 locally with manual trigger first
2. Add schedule trigger once manual trigger works
3. Build and test Workflow 5 with manual trigger
4. Add schedule trigger to Workflow 5
5. Run all WS-B and WS-C tests in [WORK-SELECTION-TESTS.md](WORK-SELECTION-TESTS.md)
6. Once all tests pass, document and prepare for Phase 2 (other workflows)

---

## Post-implementation tasks

- [ ] Remove hardcoded test IDs from GGD 04 manual trigger
- [ ] Document any workflow-specific delays or timeouts discovered
- [ ] Update PROJECT-STATUS.md with completion date
- [ ] Prepare for C0 proof test (error handler validation)
- [ ] Schedule next phase: Workflow 1 (qualification) and Workflow 2 (draft queue)

