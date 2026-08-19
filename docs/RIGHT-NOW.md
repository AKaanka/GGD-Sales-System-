# RIGHT NOW — Next 30 Minutes

## **Step 1: Commit (2 min)**

```bash
cd "/Users/kaan/Desktop/GGD -Sales-System "
git add -A docs/ odoo/ scripts/ workflows/
git commit -m "Addon: stamp approval metadata; fix WORK-SELECTION field name; add audit & roadmap"
git log --oneline -3
```

**Expected:** Commit shows addon changes + new docs (FIELD-AUDIT, ADDON-WORK-SUMMARY, COMPLETION-ROADMAP, etc.)

---

## **Step 2: Close Stale n8n Tabs (1 min)**

⚠️ **CRITICAL** — An open n8n editor tab will overwrite your fixes

1. Open n8n: `http://localhost:5678`
2. Find any open editor tabs (should show GGD 03, GGD 04, etc.)
3. **Close them all** (don't save, just close)
4. Verify workflow list shows workflows exist but none are open

---

## **Step 3: Verify B1 is Ready (1 min)**

In Odoo (`http://localhost:8069`):
- [ ] Open record 4 (WS-F2 or your test lead)
- [ ] `ggd_outreach_approved` = **TRUE**
- [ ] `ggd_last_send_key` = **(empty)**
- [ ] `ggd_do_not_contact` = **FALSE**
- [ ] Contact basis = **(has a value)**

If any of these are wrong, fix them before running B1.

---

## **Step 4: Run B1 (15 min)**

In n8n:
1. Open Workflow 3 (GGD 03 - Approved Send)
2. Click **Test workflow** (the button that runs manual trigger)
3. Watch all nodes complete:
   - Query Approved Opportunities → green ✅
   - Validate Approval Rules → green ✅
   - Claim Send Key → green ✅
   - Generate Draft → green ✅
   - Send Email → green ✅
   - Record send and consume approval → green ✅
   - Finalize Send → green ✅

**If any node turns RED:** Screenshot it and note the error message.

**If all nodes turn GREEN:** Go to Step 5.

---

## **Step 5: Check Email Arrived (5 min)**

Open your test mailbox (Gmail, Zoho, or whatever you set up):
- [ ] Did the email arrive?
- [ ] From: (what address shows?)
- [ ] Subject: (what does it say?)
- [ ] Body: (does it look right?)
- [ ] Timestamp: (when did it arrive?)

**Record:** Email arrived? **YES / NO**  
**From:** _______________

---

## **Step 6: Verify Odoo Updated (3 min)**

Back in Odoo, refresh record 4:
- [ ] `ggd_outreach_approved` = **FALSE** (revoked)
- [ ] `ggd_outreach_approved_by` = **(empty)**
- [ ] `ggd_outreach_approved_at` = **(empty)**
- [ ] `ggd_last_send_key` = **(has a value, like "4-...")**
- [ ] `ggd_last_sent_at` = **today's date + time**
- [ ] `ggd_last_message_date` = **today's date**
- [ ] Chatter note = **"GGD outreach sent..."** or similar

**Record:**
```
ggd_outreach_approved: TRUE / FALSE
ggd_last_send_key: ________________
ggd_last_message_date: ________________
Email arrived: YES / NO
```

---

## **IF B1 PASSED (all green, email arrived, Odoo updated)**

**Congratulations.** The approval → send → finalize chain works.

**Next:**
1. Run B2–B5 tests (follow [SECTION-B-EXECUTION.md](SECTION-B-EXECUTION.md))
2. Run C0 error-handler proof (follow [C0-PROOF-WALKTHROUGH.md](C0-PROOF-WALKTHROUGH.md))
3. Once those pass, move to work-selection layer

**Time estimate for B2–B5:** 1–2 hours

---

## **IF B1 FAILED (red node, email didn't arrive, Odoo not updated)**

**Don't panic.** This is debugging time.

**Checklist:**
1. [ ] Was there an error in n8n? **What did it say?**
2. [ ] Did the workflow timeout? (check execution time)
3. [ ] Is SMTP configured? (check n8n credentials)
4. [ ] Is the test mailbox real? (can you send a test email manually?)
5. [ ] Did the claim node write 7 junk fields? (check record 4 probability field)
6. [ ] Are there stale n8n tabs open? (close them and retry)

**Record the error:**
```
Error message: ___________________________
Node that failed: ________________________
Last green node: ________________________
```

**Then:** Post the error and I can help debug.

---

## **TL;DR**

```bash
# 1. Commit
git commit -m "Addon changes + roadmap"

# 2. Close n8n tabs (use browser)

# 3. Check Odoo record 4 is ready

# 4. Run B1 workflow in n8n

# 5. Check email arrived

# 6. Check Odoo updated

# 7. Report result here
```

---

**Start now. Report back with:**
- B1 passed or failed
- If failed: error message and which node
- If passed: confirmation email details + Odoo field values

**Everything else waits for this result.**
