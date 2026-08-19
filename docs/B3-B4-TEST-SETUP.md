# B3 & B4 Test Setup — Ready to Execute

**Status:** Procedures ready, you create fixtures, run tests  
**Time estimate:** 30 min total (15 min each)  
**Expected result:** Both tests block at the right gate, no emails sent

---

## **B3: Suppression Gate Test**

### **What It Tests**
The `ggd_do_not_contact=true` flag blocks all outbound sends, overriding approval.

### **Fixture Setup (In Odoo)**

**Create a new lead with these values:**

```
Name:                          "B3 Test — Suppression Block"
Email:                         b3-suppress@ggd-qa.invalid
Contact basis:                 "Consent"
Contact-basis note:            "Test fixture for suppression gate, 2026-08-19"
ggd_outreach_approved:         TRUE (approve it)
ggd_do_not_contact:            TRUE (set this AFTER approval)
```

**Why this order?**
- Approve first (so `ggd_outreach_approved_by` and timestamp are set)
- Then mark do-not-contact (this should NOT auto-revoke — it should just block sends)

**Save and note the record ID:** ________

### **Test Execution**

**In n8n:**
1. Open Workflow 3 (GGD-03-approved-send)
2. Click "Test workflow"
3. Watch the execution:
   - Query Approved Opportunities → Should find your B3 record ✓
   - Validate Approval Rules → Check the node output
     - `ggd_do_not_contact` should read `true`
     - `canSend` should be `false` ✓
   - **Should NOT reach "Claim Send Key"** ← This is key
   - Should route to "Prepare blocked-gate review note" instead

**If it routes to Send Email:**
- The suppression gate is broken
- Suppressed contacts would be emailed (CRITICAL)
- Stop and document the failure

### **Verification (After Workflow Runs)**

**In your mailbox:**
- [ ] NO email arrives (expected)

**In Odoo (check your B3 record):**
- [ ] `ggd_outreach_approved` = TRUE (unchanged, not revoked)
- [ ] `ggd_do_not_contact` = TRUE (unchanged)
- [ ] `write_date` = unchanged (no write happened)
- [ ] Chatter note = "Outbound gate blocked — Do not contact is set" or similar

**In n8n execution log:**
- [ ] Node "Prepare blocked-gate review note" has a **green checkmark**
- [ ] Node "Send Email" is **skipped** (not executed)
- [ ] Node "Finalize Send" is **skipped** (not executed)

### **Result**

```
PASS:   ✓ No email sent
        ✓ Suppression blocked the send
        ✓ Record unchanged
        ✓ Blocked-gate note created

FAIL:   ✗ Email arrived (suppression didn't work)
        ✗ Record was modified (shouldn't be)
        ✗ Send Email node executed (should be skipped)
```

---

## **B4: Contact Basis Gate Test**

### **What It Tests**
A lead without a valid contact basis cannot be approved, so send is blocked at the approval gate.

### **Fixture Setup (In Odoo)**

**Create a new lead with these values:**

```
Name:                          "B4 Test — No Contact Basis"
Email:                         b4-nobasis@ggd-qa.invalid
Contact basis:                 (LEAVE EMPTY — do NOT fill this)
Contact-basis note:            (LEAVE EMPTY — do NOT fill this)
ggd_outreach_approved:         FALSE (leave it false, don't approve)
ggd_do_not_contact:            FALSE (leave it false)
```

**Why these values?**
- No contact basis = Can't be approved
- Not approved = Should block at approval check
- Not suppressed = Let the gate, not suppression, be the blocker

**Try to approve it (should fail with error):**
1. Click "Approve Outreach" button
2. Expected: Error message like "Record and review the contact basis before approving outreach"
3. Do NOT fill in the basis (that would fix the problem, which isn't the test)
4. Leave it unapproved and save

**Save and note the record ID:** ________

### **Test Execution**

**In n8n:**
1. Open Workflow 3 (GGD-03-approved-send)
2. Click "Test workflow"
3. Watch the execution:
   - Query Approved Opportunities → Should **NOT find** your B4 record ← This is key
     - (Because it's not approved, the query filters it out)
   - If it DOES find it, the query is broken
   - Workflow should either:
     - Return empty set → exit gracefully (Always Output Data)
     - Or skip to error handling if data is malformed

**If Send Email is reached:**
- The approval gate is broken
- Unapproved contacts would be emailed (CRITICAL)
- Stop and document the failure

### **Verification (After Workflow Runs)**

**In your mailbox:**
- [ ] NO email arrives (expected, because lead wasn't in candidate set)

**In Odoo (check your B4 record):**
- [ ] `ggd_outreach_approved` = FALSE (unchanged)
- [ ] `ggd_do_not_contact` = FALSE (unchanged)
- [ ] `write_date` = unchanged (no write happened)
- [ ] No chatter note (wasn't processed at all)

**In n8n execution log:**
- [ ] Node "Query Approved Opportunities" returns **empty or doesn't find B4** ✓
- [ ] Node "Loop Through Records" is **skipped** (nothing to loop over)
- [ ] Node "Send Email" is **not executed** ✓

### **Result**

```
PASS:   ✓ B4 record not in query results
        ✓ No email sent
        ✓ Record unchanged
        ✓ No contact-basis evidence = approval blocked

FAIL:   ✗ Email arrived (unapproved lead was sent to)
        ✗ B4 record was found by query (shouldn't be, not approved)
        ✗ Chatter note created (record was processed when it shouldn't be)
```

---

## **Execution Checklist**

### **Before You Start**

- [ ] Docker services running (Odoo, n8n)
- [ ] Odoo accessible at http://localhost:8069
- [ ] n8n accessible at http://localhost:5678
- [ ] Test mailbox ready (can receive emails)

### **Fixture Creation (You do in Odoo)**

- [ ] **B3 fixture created** — suppressed, approved
  - Record ID: ________
  - Email: b3-suppress@ggd-qa.invalid
  - `ggd_do_not_contact` = TRUE
  - `ggd_outreach_approved` = TRUE
  
- [ ] **B4 fixture created** — unapproved, no basis
  - Record ID: ________
  - Email: b4-nobasis@ggd-qa.invalid
  - `ggd_outreach_approved` = FALSE
  - Contact basis = EMPTY

### **B3 Test Execution**

- [ ] Open Workflow 3 in n8n
- [ ] Click "Test workflow"
- [ ] Watch execution complete
- [ ] Check mailbox: **NO email**
- [ ] Check B3 record in Odoo: **Unchanged**
- [ ] Check execution log: "Prepare blocked-gate review note" **GREEN**
- [ ] Check execution log: "Send Email" **SKIPPED**
- [ ] **Result: PASS ✓** or **FAIL ✗**

**B3 Result: ________**

### **B4 Test Execution**

- [ ] Open Workflow 3 in n8n
- [ ] Click "Test workflow"
- [ ] Watch execution complete
- [ ] Check mailbox: **NO email**
- [ ] Check B4 record in Odoo: **Unchanged**
- [ ] Check execution log: "Query Approved Opportunities" returns **EMPTY or no B4**
- [ ] Check execution log: "Loop Through Records" **SKIPPED**
- [ ] **Result: PASS ✓** or **FAIL ✗**

**B4 Result: ________**

### **After Both Tests**

- [ ] Both passed ✓ → Move to B5
- [ ] One or both failed ✗ → Document the failure and I'll help debug
- [ ] Commit results:
  ```bash
  git add docs/
  git commit -m "B3 and B4 pass: suppression and approval gates verified"
  ```

---

## **What Each Test Proves**

| Test | Gate Under Test | Should Block | Expected Behavior |
| --- | --- | --- | --- |
| **B3** | Suppression (`do_not_contact=true`) | YES | No email, record unchanged, review note created |
| **B4** | Approval (unapproved records) | YES | Record not in query, no email, no processing |

**Together:** All three outbound gates proven (Approval, Suppression, Contact Basis)

---

## **If Tests Fail**

**B3 fails (email arrives for suppressed contact):**
- The suppression check is broken
- Every opted-out contact could be emailed
- CRITICAL — stop and debug before proceeding

**B4 fails (unapproved contact is queried):**
- The approval filter in the query is broken
- Every unapproved lead could be emailed
- CRITICAL — stop and debug before proceeding

**Either failure:** Post the execution log and I'll help diagnose.

---

## **Time Estimate**

- Create B3 fixture: 2 min
- Create B4 fixture: 2 min
- Run B3 test: 5 min
- Run B4 test: 5 min
- Verify results: 5 min
- Commit: 1 min
- **Total: 20 min**

---

**Ready to create the fixtures and run the tests?** Reply when you've completed both, with:

```
B3 result: PASS / FAIL
B4 result: PASS / FAIL
Record IDs: B3 = ___, B4 = ___
Any errors: _______________
```

Then we move to **B5 (SMTP failure recovery test).**
