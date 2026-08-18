# Section B: Outbound Acceptance Tests (Ready to Execute)

**Status:** Ready for execution. 18 August 2026.

This document provides step-by-step procedures for B1–B5 tests. Each test sends real emails via SMTP to your test mailbox. Run in order, one at a time. Do not skip or re-order tests.

---

## **Pre-Test Checklist**

- [ ] Test mailbox ready (your email address): ________________________
- [ ] SMTP credentials configured in n8n (Zoho/Gmail/test service)
- [ ] Can receive email at test address
- [ ] Workflow 3 is working (WS-B1–B5 unit tests passed earlier)
- [ ] Backup created: `./scripts/backup.sh`
- [ ] Odoo is running on http://localhost:8069
- [ ] n8n is running on http://localhost:5678

---

## **Test B1: Basic Send Succeeds (20 min)**

### **Objective**
Prove Workflow 3 sends a real email, marks the record as sent, and revokes approval.

### **Setup**

1. **In Odoo:**
   - Find record WS-F1 (or create new approved opportunity)
   - Verify state before test:
     - ggd_outreach_approved: ________________________ (should be TRUE)
     - ggd_last_send_key: ________________________ (should be EMPTY)
     - ggd_do_not_contact: ________________________ (should be FALSE)

2. **Record baseline email state:**
   - Open your test mailbox
   - Note current unread count: ________________________
   - Delete any previous test emails to keep clean

### **Execution**

1. **In n8n:**
   - Open Workflow 3 (GGD 03 - Approved Send)
   - Click "Test workflow" (manual trigger)
   - Monitor execution through all nodes:
     - Query Approved Opportunities: should find WS-F1
     - Validate Approval Rules: should pass (canSend=true)
     - Claim Send Key: should return true (key claimed)
     - Generate Draft: should create subject/body
     - Send Email: should succeed (green checkmark)
     - Finalize Send: should complete

2. **Monitor for completion:**
   - Wait for all nodes to complete (green)
   - Check for any errors (red nodes)
   - Execution time should be <30 seconds

### **Verification**

1. **Email received:**
   - [ ] Check test mailbox
   - [ ] Email arrived from SMTP sender
   - [ ] Subject line contains expected text
   - [ ] Body contains approval/outreach content
   - [ ] Email timestamp: ________________________

2. **Record updated in Odoo:**
   - [ ] Refresh WS-F1 record
   - [ ] ggd_last_send_key: ________________________ (should be POPULATED)
   - [ ] ggd_last_sent_at: ________________________ (should be CURRENT TIME)
   - [ ] ggd_last_message_date: ________________________ (should be TODAY)
   - [ ] ggd_outreach_approved: ________________________ (should be FALSE, revoked)
   - [ ] ggd_outreach_approved_by: ________________________ (should be FALSE)
   - [ ] ggd_outreach_approved_at: ________________________ (should be FALSE)

3. **Chatter note:**
   - [ ] New note created
   - [ ] Contains: "GGD outreach sent" or similar

### **Result**

- [ ] PASS: Email sent, record marked sent, approval revoked
- [ ] FAIL: Issue: ________________________

---

## **Test B2: Idempotency — Re-Run Blocked (10 min)**

### **Objective**
Prove that re-running Workflow 3 on the same record does NOT send a second email (send-key prevents it).

### **Setup**

1. **Verify WS-F1 state from B1:**
   - ggd_last_send_key: ________________________ (should be POPULATED from B1)
   - ggd_outreach_approved: ________________________ (should be FALSE from B1)

2. **Email baseline:**
   - Note current mailbox unread count: ________________________

### **Execution**

1. **In n8n:**
   - Open Workflow 3
   - Click "Test workflow" again (same record)
   - Monitor execution:
     - Query should find WS-F1 again
     - Validate should pass (wait, approved=false now, so it might fail here)
     - If Validate passes: Claim Send Key should return FALSE (key already claimed)
     - Workflow should stop before SMTP

2. **Check execution:**
   - Should complete without error (even though key already claimed)
   - Should NOT reach Send Email node

### **Verification**

1. **No second email:**
   - [ ] Check mailbox unread count
   - [ ] Count unchanged (no new email)
   - [ ] Only ONE email from B1 present

2. **Record unchanged:**
   - [ ] ggd_last_send_key: ________________________ (same as B1)
   - [ ] ggd_last_sent_at: ________________________ (same as B1)

3. **Send-key claim:**
   - [ ] Inspect Claim Send Key node output
   - [ ] Should show: result=false or similar (key rejected)

### **Result**

- [ ] PASS: No second email, send-key claim returned false
- [ ] FAIL: Issue: ________________________

---

## **Test B3: Suppression Guard (10 min)**

### **Objective**
Prove that suppressed contacts (ggd_do_not_contact=true) do NOT receive email, even if approved.

### **Setup**

1. **In Odoo:**
   - Find or create WS-F2 (suppressed contact)
   - Verify state:
     - ggd_do_not_contact: ________________________ (should be TRUE)
     - ggd_outreach_approved: ________________________ (should be TRUE)
     - ggd_contact_basis: ________________________ (should be set)

2. **Email baseline:**
   - Note mailbox unread: ________________________

### **Execution**

1. **Prepare test input:**
   - Get WS-F2 opportunity_id: ________________________
   - Create test payload with WS-F2 details (use test-inputs-workflow3.json as template)

2. **In n8n:**
   - Open Workflow 3
   - Set manual trigger input to WS-F2 data
   - Click "Test workflow"
   - Monitor execution:
     - Validate Approval Rules: should FAIL (canSend=false)
     - Violations should include: "ggd_do_not_contact is true"
     - Should route to review/error path (NOT SMTP)

### **Verification**

1. **No email sent:**
   - [ ] Check mailbox
   - [ ] No new email to WS-F2's address
   - [ ] Unread count unchanged from baseline

2. **Review note created:**
   - [ ] In Odoo, check WS-F2 chatter
   - [ ] New note explains: "ggd_do_not_contact is true" or similar
   - [ ] Note is readable and actionable

3. **Send-key NOT claimed:**
   - [ ] WS-F2 ggd_last_send_key: ________________________ (should still be EMPTY)

### **Result**

- [ ] PASS: No email sent, review note created, suppression guard worked
- [ ] FAIL: Issue: ________________________

---

## **Test B4: Basis-Missing Guard (10 min)**

### **Objective**
Prove that records without a contact basis do NOT send, even if approved.

### **Setup**

1. **In Odoo:**
   - Create test record (or use WS-F3)
   - Set:
     - ggd_contact_basis: [EMPTY/NULL]
     - ggd_contact_basis_note: [EMPTY/NULL]
     - ggd_outreach_approved: TRUE
     - ggd_do_not_contact: FALSE

2. **Record ID: ________________________**
3. **Email baseline:** ________________________

### **Execution**

1. **In n8n:**
   - Open Workflow 3
   - Set trigger to point to basis-missing record
   - Click "Test workflow"
   - Monitor:
     - Validate Approval Rules: should FAIL
     - Violations should include: "ggd_contact_basis is empty"
     - Route to review path (no SMTP)

### **Verification**

1. **No email:**
   - [ ] Mailbox unchanged
   - [ ] No email to record's address

2. **Review note:**
   - [ ] Chatter note created
   - [ ] Explains basis requirement

### **Result**

- [ ] PASS: Basis validation blocked send
- [ ] FAIL: Issue: ________________________

---

## **Test B5: Error Recovery (20 min)**

### **Objective**
Prove that send-key idempotency protects against mid-send crashes and allows recovery without duplicates.

### **Setup**

1. **Create new approved opportunity:**
   - Name: B5-Test-Recovery
   - Email: your-test+b5@example.com (unique)
   - Contact basis: set properly
   - Approved: TRUE
   - Do not contact: FALSE
   - Record ID: ________________________

2. **Intentionally break SMTP:**
   - In n8n, edit SMTP credentials
   - Change password to wrong value: `wrong-password-for-test`
   - Or change SMTP server to non-existent address: `smtp.invalid`
   - Save changes

3. **Email baseline:** ________________________

### **Execution Part 1: Cause Failure**

1. **In n8n:**
   - Open Workflow 3
   - Set trigger to B5 record
   - Click "Test workflow"
   - Monitor:
     - Should progress through Query, Validate, Claim Send Key (succeeds)
     - Should reach Send Email node
     - Should FAIL with SMTP error (credentials wrong or server unreachable)

2. **Verify failure:**
   - [ ] Send Email shows red (error)
   - [ ] Error message: ________________________
   - [ ] Check Odoo — record should have ggd_last_send_key populated (claim happened before SMTP failed)

### **Execution Part 2: Fix Credentials**

1. **Fix SMTP:**
   - In n8n, restore correct SMTP credentials
   - Save

2. **Re-run:**
   - Click "Test workflow" again on same B5 record
   - Monitor:
     - Query: finds B5
     - Validate: passes
     - Claim Send Key: should return FALSE (key already claimed from part 1)
     - Should stop before SMTP (no duplicate attempt)

### **Verification**

1. **Only one email in mailbox:**
   - [ ] Search for B5 test emails
   - [ ] Count: ________________________ (should be 1, not 2)
   - [ ] Email arrived successfully on second run

2. **Record state:**
   - [ ] ggd_last_send_key: ________________________ (same from part 1)
   - [ ] ggd_last_sent_at: ________________________ (updated on second run)
   - [ ] ggd_outreach_approved: FALSE (revoked)

3. **Send-key claim logic:**
   - [ ] Inspect second run "Claim Send Key" output
   - [ ] Shows: result=false (prevented resend)

### **Result**

- [ ] PASS: Failure didn't send, recovery on fix succeeded, no duplicate
- [ ] FAIL: Issue: ________________________

---

## **Section B Summary**

| Test | Status | Evidence |
| --- | --- | --- |
| B1: Basic send | ☐ PASS | Email received, record marked |
| B2: Idempotency | ☐ PASS | No second email, key blocked |
| B3: Suppression | ☐ PASS | No email to suppressed contact |
| B4: Basis guard | ☐ PASS | Basis validation prevented send |
| B5: Error recovery | ☐ PASS | One email after fix, no duplicate |

**All pass?** ☐ YES → Ready for Backup/Restore
**Any failures?** ☐ YES → Document above, investigate

---

## **Troubleshooting**

### **Email not arriving**
- Check SMTP credentials (re-verify in n8n)
- Check test mailbox spam folder
- Verify sender address is correct
- Check n8n logs for SMTP errors: `docker compose logs n8n --tail 100 | grep -i smtp`

### **Approval validation unexpectedly failing**
- Re-check record state in Odoo (refresh page)
- Verify contact basis is set
- Verify contact basis note meets minimum length (20 chars)
- Verify do_not_contact is FALSE

### **Send-key claim returns true when it should return false**
- Verify you're running on the SAME record as previous test
- Check ggd_last_send_key in Odoo — should be populated from previous run
- If not, previous send may have failed; run error recovery test

### **Workflow doesn't progress past a node**
- Click the node to inspect its output
- Check error message
- Verify previous node's output is correct format
- Check Odoo connectivity (if node reads from Odoo)

---

## **Sign-Off**

All Section B tests complete and passing?

**Date completed:** ________________________
**Tester:** ________________________
**Notes:** ________________________

Next: Backup and Restore Drill (SECTION-C-BACKUP-RESTORE.md)

