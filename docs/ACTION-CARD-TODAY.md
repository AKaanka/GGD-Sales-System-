# ACTION CARD — What To Do RIGHT NOW

**Status:** B1 partial pass (email sent, send-key not written)  
**Root cause:** Fixed ✓  
**Blocking issue:** Audit record node unclear

---

## **QUESTION FOR YOU (5 min)**

The node "Prepare send audit record" is incomplete. I need to know what it should do:

**A. What's the output?**
- [ ] Write to Odoo chatter (notes on the lead record)?
- [ ] Create an activity (task on the lead)?
- [ ] Update a field (which field?)?
- [ ] Write to a separate audit log?
- [ ] Other: _______________

**B. What's the "trailing-period reference" that's broken?**
- Is it a date field? (format mismatch?)
- Is it a field reference? (doesn't exist?)
- Is it missing data? (node doesn't receive it?)
- Other: _______________

**C. What data should be recorded?**
- Send timestamp?
- Email subject & body?
- Recipient address?
- Message ID?
- Approval timestamp?
- All of above?

**Reply with answers A + B + C, then proceed to next steps.**

---

## **AFTER YOU CLARIFY AUDIT RECORD (30 min)**

### Step 1: Re-Approve Record 4 (2 min)

**In Odoo:**
```
1. Go to CRM → Leads
2. Open record 4 (or your test lead)
3. Check current state:
   - ggd_outreach_approved: FALSE (was consumed by B1)
   - ggd_contact_basis: (has a value)
   - ggd_contact_basis_note: (has evidence)
4. If missing, fill them in
5. Click "Approve Outreach" button
6. Record should show:
   - ggd_outreach_approved: TRUE ✓
   - ggd_outreach_approved_by: (your user) ✓
   - ggd_outreach_approved_at: (current time) ✓
```

### Step 2: Run B1 Retest (15 min)

**In n8n:**
```
1. Open Workflow 3 (GGD-03-approved-send)
2. Click "Test workflow" (manual trigger)
3. Watch nodes:
   Query Approved Opportunities → green ✓
   Validate Approval Rules → green ✓
   Claim Send Key → green ✓ (THIS ONE SHOULD WORK NOW)
   Generate Draft → green ✓
   Send Email → green ✓
   (Audit record node) → ? (depends on fix)
   Finalize Send → green ✓
4. If any RED → screenshot it, note the error
5. If all GREEN → continue to step 3
```

### Step 3: Verify Email & Odoo (5 min)

**In mailbox:**
```
Check: Did email arrive this time?
Email arrived: YES / NO
```

**In Odoo (refresh record 4):**
```
Check these fields:
✓ ggd_last_send_key: (should have a value, like "4-...")
✓ ggd_outreach_approved: FALSE (should be revoked)
✓ ggd_last_sent_at: (should show current time)
✓ ggd_last_message_date: (should be today)
```

### Step 4: Commit (2 min)

**If B1 PASSED:**
```bash
cd "/Users/kaan/Desktop/GGD -Sales-System "
git add -A
git commit -m "B1 retest pass: claim node fixed, send-key verified, audit record complete"
git log --oneline -1
```

**If B1 FAILED:**
```
Post the error message and I'll debug with you
```

---

## **AFTER B1 PASSES**

Next: Open `docs/SECTION-B-EXECUTION.md` and run B2–B5 tests (1–2 hours)

---

## **ANSWER AUDIT RECORD QUESTION FIRST**

Your answer determines whether the audit record fix is 5 minutes or 30 minutes.

Once you clarify, I'll:
1. Read the node config
2. Diagnose what's broken
3. Fix the field reference
4. Verify the write succeeds
5. Then you can rerun B1 with the fix in place

---

**JUST REPLY WITH:**
```
A. Audit record should: _______________
B. Trailing-period reference is broken because: _______________
C. Data to record: _______________
```

**Then do steps 1–4 above.**

Everything else waits for this.
