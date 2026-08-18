# Work-Selection Layer Test Checklist

**Status:** Ready for test execution. 18 August 2026.

Use this checklist to validate each acceptance test as you build and test Workflow 3 and Workflow 5. Tick off each test as it passes.

---

## Pre-Test Setup

Before running any tests:

- [ ] Test fixtures created: Run `bash scripts/setup-work-selection-fixtures.sh`
  - Record the fixture IDs: WS-F1=___, WS-F2=___, WS-F3=___, WS-F4=___, WS-F5=___
- [ ] Backup created: `./scripts/backup.sh`
- [ ] Odoo is running on http://localhost:8069
- [ ] n8n is running on http://localhost:5678
- [ ] SMTP credentials configured in n8n (or use a test mailbox)
- [ ] LLM (Anthropic) API key configured in n8n
- [ ] Odoo automation user credential saved in n8n

---

## Phase 1: Workflow 3 (Approved Send)

### WS-B1 — Candidate Query Finds Approved Opportunities

**Test:** Workflow 3 query returns WS-F1 in candidate set.

**Setup:**
- [ ] WS-F1 (approved, unsuppressed, valid basis) created ✓
- [ ] Workflow 3 built with "Query Approved Opportunities" node ✓

**Execution:**
1. [ ] Open Workflow 3 in n8n
2. [ ] Click "Test workflow" (manual trigger)
3. [ ] Observe "Query Approved Opportunities" node output
4. [ ] Verify result contains WS-F1 record
5. [ ] Verify WS-F5 (already sent) is NOT in results

**Expected result:**
- [ ] WS-F1 id in results
- [ ] No errors
- [ ] Query filtered on ggd_outreach_approved=true AND ggd_do_not_contact=false

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-B2 — Send Succeeds, Record Marked, Approval Revoked

**Test:** Complete send workflow: claim key → SMTP → finalize.

**Setup:**
- [ ] WS-F1 ready (approved, no send-key claimed yet)
- [ ] Workflow 3 fully built (3.1–3.11 nodes)
- [ ] SMTP test mailbox configured (your email only)
- [ ] LLM draft generation working

**Execution:**
1. [ ] Trigger Workflow 3 manually
2. [ ] Monitor execution through all nodes
3. [ ] Verify email received in test mailbox
4. [ ] Check Odoo record WS-F1:
   - [ ] ggd_last_send_key: populated (not empty)
   - [ ] ggd_last_sent_at: set to current time
   - [ ] ggd_last_message_date: set to today
   - [ ] ggd_outreach_approved: FALSE (revoked after send)
   - [ ] ggd_outreach_approved_by: FALSE
   - [ ] ggd_outreach_approved_at: FALSE
5. [ ] Check Odoo chatter: "GGD outreach sent" note present

**Expected result:**
- [ ] Email in inbox
- [ ] All WS-F1 metadata correct
- [ ] Approval revoked

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Email received at:** _______________________

**Notes:** ___________________________________________________________

---

### WS-B3 — Re-Run Prevented by Send-Key Idempotency

**Test:** Re-running workflow does not send second email (send-key already claimed).

**Setup:**
- [ ] WS-B2 passed (send-key already in WS-F1)
- [ ] SMTP still configured
- [ ] Test mailbox ready

**Execution:**
1. [ ] Trigger Workflow 3 again (immediately after WS-B2)
2. [ ] Monitor "Claim Send Key" node
3. [ ] Verify it returns FALSE
4. [ ] Verify workflow stops before SMTP
5. [ ] Check test mailbox: NO second email

**Expected result:**
- [ ] Send-key claim returns false
- [ ] No SMTP attempt
- [ ] Zero duplicate emails in mailbox
- [ ] WS-F1 record unchanged

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-B4 — Suppression Guard: Do-Not-Contact Skips Send

**Test:** WS-F2 (suppressed) does not receive email.

**Setup:**
- [ ] WS-F2 (approved BUT ggd_do_not_contact=true) created ✓
- [ ] Workflow 3 in candidate query includes WS-F2 (it's approved)
- [ ] Approval validation guard in place (3.5 node)

**Execution:**
1. [ ] Modify Workflow 3 to test WS-F2 specifically (use manual trigger with WS-F2 id)
   OR
   [ ] Clear WS-F1's send-key so it appears in candidate query again, add WS-F2 to query
2. [ ] Trigger Workflow 3
3. [ ] Observe "Validate Approval Rules" node output for WS-F2
4. [ ] Verify canSend=false and violations include suppression flag
5. [ ] Verify workflow routes to review path (not SMTP)
6. [ ] Check test mailbox: NO email to ws-f2@ggd-qa.invalid

**Expected result:**
- [ ] WS-F2 has canSend=false
- [ ] No email sent
- [ ] Chatter note created on WS-F2 explaining rejection

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-B5 — Basis-Missing Guard: Validation Prevents Send

**Test:** Record without ggd_contact_basis does not send.

**Setup:**
- [ ] Create a test record (WS-F-BASIS-MISSING) with:
  - ggd_outreach_approved = true
  - ggd_do_not_contact = false
  - ggd_contact_basis = empty/null
- [ ] Workflow 3 candidate query would include it (approved, not suppressed)

**Execution:**
1. [ ] Trigger Workflow 3 with basis-missing record
2. [ ] Observe "Validate Approval Rules" node
3. [ ] Verify canSend=false, violations include "ggd_contact_basis is empty"
4. [ ] Workflow routes to review/error path
5. [ ] No SMTP attempt
6. [ ] Chatter note created

**Expected result:**
- [ ] Basis check fails
- [ ] No email
- [ ] Review note explains why

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

## Phase 2: Workflow 5 (Daily Follow-Up)

### WS-B6 — Follow-Up Query Finds Stale Opportunities

**Test:** WS-B-F4 (14 days old) in query results; WS-F5 (3 days old) excluded.

**Setup:**
- [ ] WS-F4 (14 days old message) created ✓
- [ ] WS-F5 (3 days old message) created ✓
- [ ] Workflow 5 built with "Query Stale Opportunities" node

**Execution:**
1. [ ] Trigger Workflow 5 manually
2. [ ] Observe query results
3. [ ] Verify WS-F4 is in results
4. [ ] Verify WS-F5 is NOT in results

**Expected result:**
- [ ] WS-F4 returned
- [ ] WS-F5 excluded
- [ ] Query correctly filters on ggd_last_message_date < today - 7 days

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-B7 — Follow-Up Queue Generates Draft and Activity

**Test:** Activity created on WS-F4 with draft in description.

**Setup:**
- [ ] WS-F4 ready (14 days old, not suppressed)
- [ ] Workflow 5 fully built (5.1–5.7 nodes)
- [ ] LLM draft generation working

**Execution:**
1. [ ] Trigger Workflow 5
2. [ ] Check Odoo record WS-F4:
   - [ ] New activity created (type: Follow-up)
   - [ ] Date deadline set (tomorrow or similar)
   - [ ] Activity note contains generated draft
   - [ ] NO email sent (status: draft only)
3. [ ] Check chatter: "GGD: Follow-up draft created" note present

**Expected result:**
- [ ] Activity visible in WS-F4
- [ ] Draft readable in activity
- [ ] No automation-generated emails sent

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-B8 — Follow-Up Respects Suppression and Won Status

**Test:** Suppressed records and won/lost stage get no activity.

**Setup:**
- [ ] WS-F4 (control, 14 days old, not suppressed) — should get activity
- [ ] WS-F2 (14 days old, suppressed=true) — should NOT get activity
- [ ] WS-F-WON (14 days old, stage=Won) — should NOT get activity (create this)

**Execution:**
1. [ ] Create WS-F-WON with stage=Won and ggd_last_message_date 14 days ago
2. [ ] Trigger Workflow 5
3. [ ] Check WS-F4: NEW activity created
4. [ ] Check WS-F2: NO new activity
5. [ ] Check WS-F-WON: NO new activity

**Expected result:**
- [ ] Only non-suppressed, non-won records get follow-up
- [ ] Suppression and stage filters work

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

## Integration Tests — Error Handling

### WS-C1 — Send Fails Gracefully (Odoo Down)

**Test:** Workflow 3 fails cleanly if Odoo becomes unavailable mid-send.

**Setup:**
- [ ] WS-F1 with empty send-key (ready to send)
- [ ] Workflow 3 ready to run
- [ ] Odoo running

**Execution:**
1. [ ] Note WS-F1's current state (empty send-key, approved)
2. [ ] Start Workflow 3 execution
3. [ ] When execution reaches "Query Approved Opportunities" node, stop Odoo container:
   `docker compose stop odoo` (NOT the database)
4. [ ] Workflow should error at Odoo query
5. [ ] Error handler (GGD 99) should fire (once C0 proof is settled)
6. [ ] Restart Odoo: `docker compose start odoo`
7. [ ] Check GGD 99 execution history for new entry
8. [ ] Re-read WS-F1: ggd_last_send_key should STILL be empty
9. [ ] Re-trigger Workflow 3: should find WS-F1 again and send (idempotent)

**Expected result:**
- [ ] WS-F1 not modified during failed run
- [ ] No partial write (send-key not claimed)
- [ ] Error logged sanitized (no secrets)
- [ ] Retry succeeds on Odoo restart

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Odoo stop/start time:** _________________

**Notes:** ___________________________________________________________

---

### WS-C2 — Send-Key Write Succeeds, SMTP Fails (Mid-Flight Crash)

**Test:** If SMTP fails after send-key is claimed, retry is prevented.

**Setup:**
- [ ] SMTP credential misconfigured (wrong password, or service stopped)
- [ ] WS-F1 ready (approved, empty send-key)
- [ ] Workflow 3 complete

**Execution:**
1. [ ] Trigger Workflow 3
2. [ ] Monitor execution through "Claim Send Key" (succeeds, key claimed)
3. [ ] Observe "Send Email" node fails (SMTP error)
4. [ ] Check WS-F1: ggd_last_send_key IS populated (write happened before SMTP)
5. [ ] Fix SMTP (restore credentials)
6. [ ] Re-trigger Workflow 3
7. [ ] Observe "Claim Send Key" returns FALSE (key already claimed)
8. [ ] Workflow stops before SMTP attempt
9. [ ] Check mailbox: only ONE email (no duplicate)

**Expected result:**
- [ ] Send-key claimed BEFORE SMTP (prevents duplicates on crash)
- [ ] SMTP failure is clean (no send-key write rolled back)
- [ ] Retry prevented by idempotency check

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**SMTP failure method:** _______________________

**Notes:** ___________________________________________________________

---

## Schedule Trigger Tests

### WS-D1 — Workflow 3 Runs on 15-Minute Schedule

**Test:** Workflow 3 executes automatically every 15 minutes (once schedule trigger is added).

**Setup:**
- [ ] Workflow 3 manually triggered and tested (WS-B1–B5 pass) ✓
- [ ] Schedule trigger node added (every 15 minutes)
- [ ] Workflow 3 set to INACTIVE for now (will activate later)

**Execution:**
1. [ ] Note current time: _______________
2. [ ] Activate Workflow 3 (set to active)
3. [ ] Wait 15 minutes
4. [ ] Check Workflow 3 execution history
5. [ ] Verify one auto-execution occurred (in addition to manual triggers)
6. [ ] **Immediately deactivate Workflow 3**
7. [ ] Verify no further executions after deactivation

**Expected result:**
- [ ] Auto-execution on 15-minute interval
- [ ] Execution ID in history
- [ ] Workflow executes without manual trigger

**Activation time:** _______________________  
**Expected auto-run at:** ___________________

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

### WS-D2 — Workflow 5 Runs at 08:30 Berlin Time (Working Days)

**Test:** Workflow 5 executes on schedule (daily 08:30 CET/CEST, Mon–Fri).

**Setup:**
- [ ] Workflow 5 manually tested (WS-B6–B8 pass) ✓
- [ ] Cron trigger configured (08:30 Europe/Berlin, Mon–Fri only)
- [ ] Workflow 5 set to INACTIVE for now

**Execution:**
1. [ ] Note current time and day: _______________
2. [ ] If today is a weekday (Mon–Fri):
   - [ ] Activate Workflow 5
   - [ ] Wait until tomorrow 08:30 Berlin time
   - [ ] Check execution history for auto-run at exactly 08:30
3. [ ] If today is weekend:
   - [ ] Activate Workflow 5
   - [ ] Wait until Monday 08:30 Berlin time
   - [ ] Check execution history for Monday auto-run only
4. [ ] **Immediately deactivate Workflow 5**
5. [ ] Verify no execution on next weekend (if applicable)

**Expected result:**
- [ ] Auto-execution at exactly 08:30 Berlin time
- [ ] No execution on Saturday/Sunday
- [ ] Execution appears in history

**Activation date/time:** ________________  
**Expected run at:** ____________________ (Berlin time)

**Status:** ☐ PASS  ☐ FAIL  ☐ BLOCKED

**Notes:** ___________________________________________________________

---

## Sign-Off

Once all tests above pass, the work-selection layer is proven.

### Before Activation

- [ ] All WS-B tests pass (1–8)
- [ ] All WS-C tests pass (1–2)
- [ ] All WS-D tests pass (1–2)
- [ ] No failures recorded or documented above
- [ ] C0 proof passed (error handler fires — separate gate)
- [ ] Backups current

### Remaining Before Production Use

After work-selection layer passes, proceed with:
1. [ ] **C0 proof** — Error handler validation (2 minutes)
2. [ ] **A8 test** — Odoo unavailability recovery (15 minutes)
3. [ ] **Section B** — Actual SMTP tests to your mailbox (3-5 hours)
4. [ ] **Workflow 1 & 2** — Qualification and draft queues (parallel build)
5. [ ] **Backup and restore** — Isolated drill (1-2 hours)
6. [ ] **Legal review** — Contact-basis procedure (external calendar item)

### Sign-Off Date

**Work-selection layer approved for use:** _______________

**Approved by:** _______________________________________________

**Date:** __________________

