# Work-Selection Layer Test Specifications

**Status:** Test specifications ready for implementation. 18 August 2026.

This document defines the acceptance tests for automated candidate selection and scheduling. These tests verify that workflows can find and process their own work without manual execution.

## Test Fixtures

| Fixture | ID | Purpose | State |
| --- | --- | --- | --- |
| WS-F1 | NEW | Approved, unsuppressed, valid basis | Ready for send test |
| WS-F2 | NEW | Approved, do-not-contact (guard test) | Suppressed after test |
| WS-F3 | NEW | Draft-submitted, no approval yet | Ready for queue test |
| WS-F4 | NEW | Sent 14 days ago, no reply | Ready for follow-up test |
| WS-F5 | NEW | Sent 3 days ago (no follow-up yet) | Reusable |

Create these in the ggd database before running tests.

---

## Phase 1 Tests — Workflow 3 (Approved Send)

### WS-B1 — Candidate query finds approved opportunities

**Setup:**
- Create WS-F1 with ggd_outreach_approved=true, ggd_do_not_contact=false, valid basis and note
- Leave WS-F5 (sent 3 days ago) approved as a control

**Test:**
1. Trigger Workflow 3 manually
2. Confirm it finds WS-F1 in the candidate set
3. Confirm WS-F5 is NOT in the set (already sent, not in "awaiting send" state)

**Expected result:**
- Candidate query correctly filters on: approved=true, suppressed=false, basis not empty
- Records already sent are excluded

**Pass criteria:**
- Query returns WS-F1 only (or WS-F1 + any other legitimately approved/unsent)
- No false positives (already-sent records)

---

### WS-B2 — Send-key idempotency: first send succeeds

**Setup:**
- WS-F1 as above, ggd_last_send_key empty
- SMTP credentials configured
- Test recipient: your own test mailbox

**Test:**
1. Trigger Workflow 3
2. Observe the workflow:
   - Select WS-F1
   - Generate draft subject and body
   - Claim send key via `ggd_claim_send_key()`
   - Confirm returned true
   - Send via SMTP (use test address only)
   - Call `ggd_finalize_send()`
3. Check Odoo: WS-F1 should show:
   - ggd_last_send_key: populated with unique key
   - ggd_last_sent_at: current time
   - ggd_last_message_date: today
   - ggd_outreach_approved: false (revoked after send)
   - Chatter note about send completion
4. Check recipient mailbox: email received

**Expected result:**
- Email sent successfully
- Record marked as sent
- Approval revoked to prevent resends

**Pass criteria:**
- Email arrives
- All metadata updated correctly
- No duplicate send on immediate re-run

---

### WS-B3 — Send-key idempotency: re-run after crash

**Setup:**
- Same as WS-B2, but WS-F1 already has ggd_last_send_key populated from WS-B2
- Simulate workflow restart (e.g., by manually triggering again)

**Test:**
1. Trigger Workflow 3
2. Select WS-F1
3. Workflow calls `ggd_claim_send_key()` with the same key
4. Confirm method returns false
5. Workflow stops without calling SMTP

**Expected result:**
- No second email sent
- No record update (prevents timestamp corruption)
- Workflow exits cleanly on the false return

**Pass criteria:**
- No duplicate email in recipient mailbox
- Odoo record unchanged
- Workflow does not error; it handles "key already claimed" gracefully

---

### WS-B4 — Suppression guard: do-not-contact skips send

**Setup:**
- WS-F2 with ggd_outreach_approved=true BUT ggd_do_not_contact=true
- Valid basis and note
- SMTP credentials ready

**Test:**
1. Trigger Workflow 3
2. Confirm WS-F2 appears in candidate query (it's approved)
3. Per-record check: Workflow evaluates approval rules
4. Confirm do-not-contact check fails
5. Workflow routes to review/error path (no SMTP)
6. Chatter note added explaining why it was skipped

**Expected result:**
- WS-F2 is NOT sent to
- No SMTP call made
- Error/review note created

**Pass criteria:**
- Zero emails to suppressed address
- Record updated with skip reason
- Workflow exits gracefully (no error)

---

### WS-B5 — Basis-missing guard: approval rules rejected

**Setup:**
- WS-F1 copy with ggd_outreach_approved=true but ggd_contact_basis=null
- (Or create WS-F6 with this state)

**Test:**
1. Trigger Workflow 3
2. Confirm candidate query includes this record (approved=true, do_not_contact=false)
3. Per-record check: Workflow evaluates `_ggd_check_approval_allowed()`
4. Basis validation fails
5. Workflow routes to review/error path

**Expected result:**
- No SMTP attempt
- Error/review note created
- Human review queued

**Pass criteria:**
- Basis-missing records never send
- All approvals are verified at send time, not at approval time

---

## Phase 1 Tests — Workflow 5 (Daily Follow-up)

### WS-B6 — Follow-up query finds stale opportunities

**Setup:**
- WS-F4 with ggd_last_message_date = 14 days ago
- WS-F5 with ggd_last_message_date = 3 days ago (not stale)
- Both active, not won/lost, not suppressed

**Test:**
1. Schedule Workflow 5 for 08:30 or manually trigger
2. Confirm it finds WS-F4 in the candidate set
3. Confirm WS-F5 is NOT in the set (not yet 7 days old)

**Expected result:**
- Query correctly filters on: ggd_last_message_date < today - 7 days
- Recent messages are excluded

**Pass criteria:**
- Only truly stale records are returned
- 3-day-old message is correctly excluded

---

### WS-B7 — Follow-up queue generates draft and activity

**Setup:**
- WS-F4 as above (14 days old)
- No pending activity on the record

**Test:**
1. Trigger Workflow 5
2. Select WS-F4
3. Workflow generates follow-up draft (LLM-assisted)
4. Workflow creates Odoo activity (follow-up type)
5. Workflow logs a chatter note
6. Workflow DOES NOT SEND (initial release)

**Expected result:**
- Activity created on WS-F4 with due date (e.g., tomorrow)
- Draft stored in activity or chatter for human review
- Record not marked as sent

**Pass criteria:**
- Activity is visible in Odoo
- Draft is readable
- No email sent automatically

---

### WS-B8 — Follow-up skips suppressed and won records

**Setup:**
- WS-F4 (14 days, stale)
- WS-F2 (14 days, but ggd_do_not_contact=true)
- WS-F7 (14 days, stage=Won)

**Test:**
1. Trigger Workflow 5
2. Confirm only WS-F4 appears in results
3. WS-F2 and WS-F7 are excluded

**Expected result:**
- Suppressed records never get follow-up activity
- Won/Lost records are excluded

**Pass criteria:**
- No activity on WS-F2 or WS-F7
- Activity only on WS-F4

---

## Integration Tests — Error Handling

### WS-C1 — Send fails gracefully (Odoo down)

**Setup:**
- Workflow 3 ready
- WS-F1 approved
- SMTP configured

**Test:**
1. Stop Odoo container (not database)
2. Trigger Workflow 3
3. Workflow fails at Odoo query step
4. Error handler fires (once C0 proof is settled)
5. GGD 99 records the failure

**Expected result:**
- Sanitized error note in GGD 99
- WS-F1 ggd_last_send_key still empty (write never happened)
- Workflow exits cleanly

**Pass criteria:**
- Error logged without secrets
- Record state unchanged (idempotent)
- Re-run after Odoo restart finds WS-F1 again

---

### WS-C2 — Send-key write succeeds, SMTP fails

**Setup:**
- Workflow 3, WS-F1
- SMTP credentials WRONG or service down

**Test:**
1. Trigger Workflow 3
2. Workflow claims send key (write succeeds)
3. SMTP call fails
4. Workflow routes to error handler

**Expected result:**
- ggd_last_send_key IS populated (claim write completed)
- ggd_last_sent_at is set
- No email sent
- Error logged
- Manual recovery: fix SMTP, retry (claim will fail, prevent re-send)

**Pass criteria:**
- Send key is claimed BEFORE SMTP
- Prevents duplicate send even after mid-flight crash
- Human can investigate why email wasn't sent

---

## Schedule Trigger Tests

### WS-D1 — Workflow 3 runs on 15-minute schedule

**Test:**
1. Note the current time
2. Activate Workflow 3 (if schedule trigger exists)
3. Wait 15 minutes
4. Check Workflow 3 execution history
5. Confirm auto-execution occurred

**Expected result:**
- Workflow executed without manual trigger
- Executed on correct 15-minute interval

**Pass criteria:**
- Execution history shows multiple runs
- No manual trigger required

---

### WS-D2 — Workflow 5 runs at 08:30 Berlin time on working days

**Test:**
1. Schedule Workflow 5 for tomorrow 08:30 CET/CEST
2. Wait for scheduled time
3. Check execution history
4. Confirm auto-execution occurred

**Expected result:**
- Workflow executed at exactly 08:30
- Did not run on Saturday/Sunday (if applicable)

**Pass criteria:**
- Execution history shows correct time
- Skipped weekends if configured

---

## Sign-off Criteria

All Phase 1 tests must pass:

- [ ] WS-B1: Candidate query correctly filters
- [ ] WS-B2: Send succeeds and record marked correctly
- [ ] WS-B3: Re-run prevented by send-key idempotency
- [ ] WS-B4: Suppression guard works (no send)
- [ ] WS-B5: Basis validation works (no send)
- [ ] WS-B6: Follow-up query finds stale records
- [ ] WS-B7: Follow-up generates draft and activity
- [ ] WS-B8: Follow-up respects suppression and won status
- [ ] WS-C1: Error handling is sanitized (Odoo down)
- [ ] WS-C2: Send-key prevents resends after SMTP failure
- [ ] WS-D1: Workflow 3 schedule runs automatically
- [ ] WS-D2: Workflow 5 schedule runs at 08:30 Berlin time

Once these pass, the work-selection layer is proven and workflows can be activated for controlled use.

---

## Implementation notes for n8n builders

Each test above corresponds to a specific workflow requirement:

**Workflow 3 nodes:**
1. Schedule trigger (every 15 min)
2. Query Odoo: `crm.lead.search([('ggd_outreach_approved', '=', true), ('ggd_do_not_contact', '=', false), ...])`
3. Always Output Data node
4. Loop through results
5. Per-record:
   - Apply approval rules check
   - If denied → error path
   - If approved → claim send key
   - If claim denied → stop (key already sent)
   - If claim approved → call SMTP
   - If SMTP fails → error handler
   - If SMTP succeeds → call `ggd_finalize_send()`

**Workflow 5 nodes:**
1. Schedule trigger (08:30 Berlin, working days only)
2. Query Odoo: stale opportunities
3. Always Output Data node
4. Loop through results
5. Per-record:
   - Check suppression and stage
   - If excluded → skip
   - If included → LLM draft generation
   - Create follow-up activity in Odoo
   - Add chatter note

All nodes must reference the shared error handler (`GGD 99`).
