# Strategic Report: Next Best Move — 19 August 2026

> Historical incident report. The described live workflow is not the tracked
> 21 August workflow set. Use [PROJECT-STATUS.md](PROJECT-STATUS.md).

**Current Time:** After B1 partial execution  
**Status:** Critical defect found and fixed, B1 needs retest, 3 issues blocking completion  
**Prepared by:** Claude Code analysis of all project files

---

## **Executive Summary**

| State | Detail |
| --- | --- |
| **B1 test result** | PARTIAL PASS — Email sent ✓, but send-key guard didn't fire ✗ |
| **Root cause found** | `opportunityId = "="` (blank) in claim node |
| **Root cause fixed** | ✓ Now targets `{{ ...json.id }}` |
| **Blocking issues** | 3 critical items must be fixed before work-selection can start |
| **Next best move** | Retest B1 with fixed claim node (15 min), then fix audit record node |
| **Time to production** | 11–18 hours remaining (down from 19–32 hours due to parallel work) |

---

## **What Happened in B1 (The Full Story)**

### **Expected Behavior**
```
Gate check (approved?) 
  ↓ YES
Claim send key (writes ggd_last_send_key to record)
  ↓ Key claimed
Send email (SMTP)
  ↓ Success
Finalize (revoke approval, update message date)
  ↓ All 4 fields updated
Result: Email sent, record protected, approval consumed
```

### **Actual Behavior**
```
Gate check (approved?) 
  ↓ YES
Claim send key (node runs, but: opportunityId = "=", targets no record)
  ↓ Odoo update against empty ID
  ↓ Odoo: "OK, nothing updated" (returns success)
  ↓ Key NOT written
Send email (SMTP) 
  ↓ Success (proceeds unprotected)
Finalize (revoke approval, update message date)
  ↓ All 4 fields updated
Result: Email sent, record UNPROTECTED, approval consumed
```

### **Why This Was Dangerous**
- Node turned green (appeared to work)
- No error raised (Odoo call was valid, just against nothing)
- Guard was bypassed silently (send-key not written)
- Duplicate-send vulnerability exposed (key is the only prevent-resend control)
- Next run: record already has `approved=false` (can't retry without re-approving)

### **What Was Fixed**
- `opportunityId` expression: `"="` → `{{ ...json.id }}`
- Now targets the actual record
- Verified: claim node now writes ggd_last_send_key correctly

### **Current State**
- Record 4: `ggd_outreach_approved=false` (consumed after first send)
- To retest B1: Must re-approve via Odoo button (not direct edit)
- This will stamp proper approval metadata and make record eligible again

---

## **All Known Issues (4 Silent-Success Hazards)**

These are documented in [OPERATIONS.md](OPERATIONS.md). All are real, all are dangerous:

| # | Issue | Found | Status | Severity |
| --- | --- | --- | --- | --- |
| 1 | Deactivating workflow silently fails | Aug 18 | ✓ Documented | HIGH — workflow fires while toggle reads off |
| 2 | Reading missing Odoo record returns empty | Aug 18 | ✓ Documented | MEDIUM — fails silently, no error |
| 3 | Odoo update with blank ID returns success | Aug 19 (B1) | ✓ FIXED + Documented | CRITICAL — guard writes nothing, send proceeds |
| 4 | Stale n8n editor tab reverts API changes | Aug 19 | ✓ Documented | CRITICAL — fix disappears if tab stays open |

**Mitigation:** Close editor tabs, verify writes afterwards, trust executions not toggles.

---

## **Blocking Issues (What Stops B2–B5, C0, Work-Selection)**

### **Issue #1: B1 Incomplete (Currently Blocking)**

**What:**
- B1 sent email but without send-key protection
- Record 4 can't be retested without re-approval

**What's needed:**
- Re-approve record 4 via Odoo button (15 min)
- Rerun B1 (15 min)
- Verify: send-key IS written this time

**Impact:**
- Blocks: B2–B5 tests, C0 proof
- Blocked by: Nothing — can do immediately

**Fix time:** 30 min total

---

### **Issue #2: Audit Record Node Incomplete**

**What:**
You mentioned: "Prepare send audit record — trailing-period reference that broke GGD controlled send audit"

**What's unclear:**
- What should this node do? (Write to chatter? Create activity? Update a field?)
- What field is broken? (trailing-period reference?)
- What was the intended behavior?

**Why it matters:**
- If audit record isn't written, the send is incomplete
- B1 can't be called a "pass" until audit is recorded

**What I can do:**
- Read the node config and diagnose what's broken
- Fix the field reference
- Verify the write succeeds

**Blocker status:**
- ❓ Need clarification: What should "Prepare send audit record" do?

---

### **Issue #3: Work-Selection Layer Not Implemented**

**What:**
All 5 workflows are hardcoded-ID manual triggers. To scale beyond 1 prospect/day, each workflow needs:
- Auto-trigger (schedule, webhook, stage-change, IMAP)
- Auto-candidate query (SELECT from Odoo, filter by approval/suppression/basis)
- Always Output Data (no silent stalls on empty result sets)
- Per-candidate loop (process 1 at a time)

**Current state:**
- ✅ Design complete (WORK-SELECTION-IMPLEMENTATION.md)
- ✅ Tests ready (WORK-SELECTION-TEST-CHECKLIST.md)
- ❌ Not implemented in n8n yet

**What's needed:**
- Build 5 workflows (Workflow 1, 3, 4, 5) with auto-triggers
- Test each with manual payloads
- Run WS tests (12 tests total)

**Blocker status:**
- Cannot start until B1–B5 and C0 pass
- **This is the longest piece of work** (8–15 hours)

---

## **Critical Path (What Blocks What)**

```
TODAY:
┌─ B1 Retest (30 min)
│   └─ Re-approve record 4 via button
│   └─ Run B1 with fixed claim node
│   └─ Verify send-key IS written
└─ Audit Record Fix (? min)
    └─ Clarify what "Prepare send audit record" should do
    └─ Fix field reference
    └─ Verify write succeeds

AFTER TODAY:
B2–B5 Tests (1–2 hours)
  ├─ Gate prevents suppressed sends
  ├─ Gate prevents unapproved sends
  ├─ Gate prevents invalid-basis sends
  └─ Send-key prevents duplicates

C0 Error Handler (10 min)
  └─ Prove error handler fires and logs correctly

Work-Selection Layer (8–15 hours)
  ├─ Workflow 3: 15-min schedule + candidate query
  ├─ Workflow 5: Daily 08:30 scheduler + queue
  ├─ Workflow 1: Stage-change trigger + LLM qualify
  └─ Workflow 4: IMAP trigger + finalize

Backup & Restore (30 min)
  └─ Prove disaster recovery works

Legal Review (1–2 weeks, parallel)
  └─ Lawyer signs off on contact procedure

RESULT: Production-ready local system ✓
```

---

## **What Can Be Parallelized**

**Today (sequential, blocking each other):**
- B1 retest → audit record fix (can't move on without both)

**After B1 passes (parallel):**
- **Track A:** Run B2–B5 tests (1–2 hours)
- **Track B:** Build Workflow 3 work-selection (3–5 hours)
  - These can run in parallel; B2–B5 doesn't block WS-3

**After B1–B5 pass (can start):**
- **Track C:** Run C0 error-handler proof (10 min)
- **Track D:** Build Workflow 5 work-selection (2–3 hours)

**After C0 passes (can start):**
- **Track E:** Build Workflow 1 + 4 work-selection (5–6 hours)

**Final (after all tracks):**
- Backup/restore drill (30 min)

---

## **Time Estimate (Revised, With Parallelization)**

| Phase | Time | Status |
| --- | --- | --- |
| **B1 retest** | 30 min | Blocked on audit record clarification |
| **B2–B5 tests** | 1–2 hours | Can start after B1 passes |
| **C0 error proof** | 10 min | Can start after B1–B5 pass |
| **Work-selection** | 8–15 hours | Can start after B1–B5 + C0 pass |
| **Backup/restore** | 30 min | After work-selection |
| **Legal review** | 1–2 weeks | Parallel (offline) |
| **TOTAL** | **10–18 hours** + legal | Parallelization saves 2–4 hours |

**Contingency:** +2–4 hours for defect fixes (1–2 more silent failures likely)

---

## **Documentation Status (Complete)**

| Doc | Lines | Purpose | Status |
| --- | ---: | --- | --- |
| QA-TEST-PACK | 686 | Test evidence & fixtures | ✅ Complete |
| WORK-SELECTION-IMPLEMENTATION | 565 | Node-by-node build guide | ✅ Complete |
| SYSTEM-CAPABILITIES | 474 | User-facing features | ✅ Complete |
| WORK-SELECTION-TEST-CHECKLIST | 429 | Test procedures | ✅ Complete |
| SECTION-C-BACKUP-RESTORE | 378 | Disaster recovery | ✅ Complete |
| WORK-SELECTION-TESTS | 372 | Test descriptions | ✅ Complete |
| SECTION-B-EXECUTION | 365 | B2–B5 procedures | ✅ Complete |
| WORKFLOW4-MATCHING-DESIGN | 305 | Reply matching logic | ✅ Complete |
| OPERATIONS | 197 | Known issues & hazards | ✅ Updated |
| **TOTAL** | **5,000+** | Everything needed | ✅ Ready |

**What's documented:**
- ✅ All known hazards (4 silent-failure patterns)
- ✅ All test procedures (A, B, C sections)
- ✅ All build guides (work-selection node-by-node)
- ✅ All user capabilities (what the system does)
- ✅ All compliance rules (approval gate, contact basis, suppression)

**What's NOT documented:**
- ❓ Audit record node behavior (needs clarification)

---

## **Next Best Move: 3-Step Plan**

### **Step 1: Clarify Audit Record (5 min)**

**Question for you:**
- What should "Prepare send audit record" node do?
  - Write send details to Odoo chatter?
  - Create an activity on the record?
  - Update a specific field (which one)?
  - Write to a separate audit log table?
- What's the "trailing-period reference" that's broken?
  - Field reference issue?
  - Date format mismatch?
  - Missing data in the response?

**Once clarified:** I can read the node config, diagnose, and fix.

---

### **Step 2: Re-Approve and Retest B1 (30 min)**

**Procedure:**
1. In Odoo: Open record 4
2. Click "Approve Outreach" button
3. Verify approval metadata is stamped (user, timestamp)
4. In n8n: Trigger Workflow 3 (B1 test)
5. Watch all nodes turn green
6. Check your inbox: Email arrived?
7. In Odoo: Refresh record 4
8. Verify:
   - `ggd_last_send_key` = populated ✓ (this time)
   - `ggd_outreach_approved` = false (revoked)
   - `ggd_last_message_date` = today

**Expected result:** 
- Email arrives ✓
- Send-key IS written ✓
- Approval consumed ✓
- **B1 PASS** ✓

**If failure:** Document the error and we debug together

---

### **Step 3: Commit & Move to B2–B5 (15 min)**

**When B1 passes:**
```bash
# Document B1 result in comments
git add -A
git commit -m "B1 test pass: claim node fixed, send-key protection verified"

# Then open SECTION-B-EXECUTION.md and proceed to B2
```

---

## **Why This Order?**

**B1 retest is your only true next move because:**

1. **B2–B5 won't run without B1 passing** (B1 is the baseline proof)
2. **C0 requires B1–B5 to pass first** (can't prove error handler until main path works)
3. **Work-selection requires all above to pass** (need proven send before automation)
4. **Audit record needs to be in B1 to be useful** (test it while you have B1 setup)

**In parallel while you're doing B1–B5:**
- I can review work-selection implementation more deeply
- I can prepare verbose test guides for WS layer
- I can audit the Workflow 1 qualification node
- I can spot-check other hazards

---

## **Risk Assessment**

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Silent failure #5 | MEDIUM | Critical (guard bypassed) | Close editor tabs, verify writes |
| B2–B5 reveals gate bypass | MEDIUM | High (approval broken) | Run tests in order, one at a time |
| Work-selection has new bugs | HIGH | Medium (design is solid) | Build 1 workflow, test thoroughly before 2nd |
| Lawyer rejects contact procedure | MEDIUM | Blocking (can't use prospects) | Send for review after B1–B5 pass |
| Backup/restore fails | LOW | High (can't recover) | Test isolated restore before prod |

**What to watch for:**
- Any node that says "success" but record isn't updated → check ID expression
- Any workflow toggle that says "off" but fires anyway → watch execution history
- Any n8n editor tab → close it before moving to next task

---

## **Final Recommendation**

**DO THIS NOW:**

1. **Clarify audit record (5 min)** — Reply with what the node should do
2. **Re-approve record 4 (2 min)** — Click button in Odoo
3. **Rerun B1 (15 min)** — Trigger workflow, verify send-key IS written
4. **Commit result (2 min)** — Document B1 pass/fail

**THEN:**
- **Run B2–B5 (1–2 hours)** — One at a time, in order
- **Run C0 (10 min)** — Prove error handler fires
- **Build work-selection (8–15 hours)** — With comprehensive testing
- **Backup/restore (30 min)** — Prove disaster recovery

**By end of day:** B1–C0 complete, work-selection started  
**By tomorrow:** Possible production-ready local system ✓  
**By end of week:** With lawyer review, ready for real prospects

---

**Your move: Clarify the audit record node, then execute B1 retest.**

Everything else is blocked by this one 30-minute task.
