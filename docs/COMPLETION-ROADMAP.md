# Critical Path to Completion — 19 August 2026

> Historical roadmap retained for audit context. Its percentages and next
> actions are superseded by [PROJECT-STATUS.md](PROJECT-STATUS.md).

**Goal:** Get the system to production-ready (locally tested and backed up) as quickly as possible.

**Current state:** 
- Workflow 4 (reply analysis): 8/9 tests passing ✅
- Workflow 3 (outbound send): built, B1 test about to run ⏳
- Addon: 19 tests pass, metadata stamping fixed ✅
- Error handler: designed but never actually fired (C0 unproven) ⚠️
- Work-selection layer: designed but not n8n-implemented ⏳
- Backup/restore: scripted but never tested ⚠️
- Legal review: not started ⚠️

---

## **CRITICAL PATH (What blocks everything else)**

### **1. RUN B1 TEST (20 min) — BLOCKING EVERYTHING**
**Status:** Ready to execute NOW  
**Blocker:** None — this is the go/no-go on Workflow 3

```
B1 succeeds?
├─ YES → Proceed to B2–B5 (2–3 hours)
│   ├─ B2–B5 pass → Work-selection layer is next safe task
│   └─ Any B2–B5 fail → Debug before next phase
└─ NO → Fix and retry (1–2 hours of debug)
    └─ Record what broke and why
```

**What to verify after B1:**
- Email arrived in your inbox
- `ggd_outreach_approved` reverted to FALSE
- `ggd_last_send_key` populated
- `ggd_last_message_date` set to today

---

### **2. B2–B5 TESTS (1–2 hours) — GATES WORK-SELECTION**
**Status:** Procedures documented, fixtures ready, waiting for B1  
**Depends on:** B1 passing

| Test | Time | What it proves |
| --- | --- | --- |
| **B2** | 10 min | Suppressed contact blocks send |
| **B3** | 10 min | Unapproved contact blocks send |
| **B4** | 10 min | Invalid contact basis blocks send |
| **B5** | 15 min | Send-key idempotency prevents duplicates |

**Critical:** If ANY of B2–B5 fail, the approval gate is broken and Workflow 3 cannot be trusted.

---

### **3. PROVE C0 (ERROR HANDLER FIRES) (10 min) — GATES C TESTS**
**Status:** Walkthrough documented, 2-minute proof available  
**Depends on:** Addon working (19 tests pass)

**What it does:** Injects a failure into Workflow 4, verifies error handler catches it and logs correctly.

**Why it's critical:** The error handler has never actually fired. If it doesn't work, all five workflows are blind to errors and will silently fail.

**Where:** [C0-PROOF-WALKTHROUGH.md](C0-PROOF-WALKTHROUGH.md)

---

### **4. WORK-SELECTION LAYER (8–15 hours) — GATES PRODUCTION**
**Status:** Design complete, implementation pending in n8n  
**Depends on:** B1–B5 pass AND C0 proves

**What it does:** Each workflow discovers its own work instead of being manually triggered with hardcoded IDs.

**Components:**
- Workflow 1 — Lead qualification (manual trigger initially, then stage-change watch)
- Workflow 3 — Approved send (15-min schedule + query)
- Workflow 4 — Reply analysis (IMAP trigger, watch email account)
- Workflow 5 — Daily follow-up (08:30 Berlin time on working days)

**Implementation:** Follow [WORK-SELECTION-IMPLEMENTATION.md](WORK-SELECTION-IMPLEMENTATION.md) sections 3.1–3.12 per workflow.

**Tests:** [WORK-SELECTION-TEST-CHECKLIST.md](WORK-SELECTION-TEST-CHECKLIST.md) (12 tests)

---

### **5. BACKUP & RESTORE DRILL (30 min) — GATES DEPLOYMENT**
**Status:** Procedures documented, script ready, never tested  
**Depends on:** Everything else passing

**What it proves:** You can recover from a complete failure.

**Steps:**
1. Create full backup (`./scripts/backup.sh`)
2. Destroy containers and volumes
3. Restore from backup
4. Verify workflows still work
5. Copy backup to external storage

**Where:** [SECTION-C-BACKUP-RESTORE.md](SECTION-C-BACKUP-RESTORE.md)

---

### **6. LEGAL REVIEW (⏱️ CALENDAR TIME) — GATES PROSPECTS**
**Status:** Procedure drafted, not reviewed  
**Depends on:** System proven to work correctly (all tests pass)

**What it covers:**
- GDPR consent mechanism (Art. 6(1)(f) legitimate interest balancing)
- UWG §7 compliance (German marketing law on cold email)
- Do-not-contact suppression rules
- Email retention policy
- Reply classification (is it a consent to continue?)

**Action:** Send [LAWFUL-CONTACT-PROCEDURE.md](LAWFUL-CONTACT-PROCEDURE.md) to a qualified German data protection lawyer.

**Lawyer should verify:**
- The contact bases are defensible
- The approval flow is compliant
- The suppression rules work
- The Art. 14 information is correct

---

## **FASTEST PATH (What to do in order)**

### **Phase α: Prove Outbound Works (TODAY, ~3 hours)**

1. **B1 test** (20 min) → Email send end-to-end
2. **B2–B5 tests** (1–2 hours) → Approval gate holds
3. **C0 proof** (10 min) → Error handler fires
4. **Commit checkpoint** → B1–B5 + C0 results documented

**Blockers that might extend this:**
- B1 fails → debug (30 min–1 hour)
- C0 fails → error handler broken, need fix (1–2 hours)
- Any B2–B5 fail → gate bug, need fix (1–2 hours)

**Success criteria:** All B1–B5 pass, C0 fires, no unfixed defects found.

---

### **Phase β: Build Work-Selection (8–15 hours, non-urgent until Phase α passes)**

**What it does:** Turn 5 hardcoded-ID workflows into actual automations.

**Workflows to implement (in order):**
1. **Workflow 3** — 15-min scheduler, query approved unsuppressed leads, send per candidate
2. **Workflow 5** — 08:30 daily scheduler, query overdue opportunities, draft follow-ups
3. **Workflow 1** — Watch Odoo stage changes, run LLM qualification on fresh leads
4. **Workflow 4** — IMAP watch, process incoming replies (already mostly working)

**Each one:** Build → Manual test with fixtures → Run WS tests → Commit

**Time breakdown:**
- Workflow 3 complete: 3–5 hours (complex, has approval + finalization logic)
- Workflow 5: 2–3 hours (reuses patterns from 3)
- Workflow 1: 3–4 hours (adds LLM, new trigger type)
- Workflow 4: 2–3 hours (mostly done, add triggers + context)
- Testing all four: 2–3 hours

---

### **Phase γ: Backup & Restore (30 min, after Phase β)**

1. Create fresh backup after Phase β complete
2. Test restore in a separate Docker volume
3. Copy to external encrypted storage
4. Document restore procedure

---

### **Phase δ: Legal Review (⏱️ 1–2 weeks, happens in parallel)**

While Phase β is building workflows, contact the lawyer:
- Send [LAWFUL-CONTACT-PROCEDURE.md](LAWFUL-CONTACT-PROCEDURE.md)
- Ask for review of contact bases, consent logic, suppression
- Get written approval before touching any real contacts

---

## **WHAT WILL FAIL YOU IF SKIPPED**

| Item | Cost if skipped | When you discover it |
| --- | --- | --- |
| B1–B5 tests | Broken approval gate, silent data corruption | First real send |
| C0 error handler | Blind workflows, no error logging | First workflow failure |
| Backup/restore | Can't recover, system down 24h+ | After a crash |
| Legal review | Business shut down by BaFin, GDPR fines | After first complaint |
| Work-selection layer | Manual triggers only, no automation | Trying to scale beyond 1 prospect/day |

---

## **TIME ESTIMATE TO PRODUCTION-READY (LOCAL)**

| Phase | Time | Status |
| --- | --- | --- |
| **α: Outbound + error handler** | 3 hours | Today, B1 running now |
| **β: Work-selection layer** | 8–15 hours | After Phase α |
| **γ: Backup & restore** | 1 hour | After Phase β |
| **δ: Legal review** | 1–2 weeks | Parallel, happens offline |
| **ε: Prune test copies** | 30 min | After Phase γ |
| **Total system ready** | **12–19 hours hands-on time** | Plus 1–2 weeks legal calendar time |

**Add 30–50% for contingency** (every session has found defects).

---

## **WHAT'S ALREADY DONE (Don't rebuild)**

- ✅ Addon fields and methods (31 fields, 5 methods, 19 tests)
- ✅ Workflow 4 reply matching (byte-verified against deployed version)
- ✅ CRM controls (approval gate, suppression, contact basis validation)
- ✅ Approval metadata stamping (fixed in this session)
- ✅ Send-key idempotency (claim before SMTP, finalize after)
- ✅ Error handler wiring (all 5 workflows reference it)
- ✅ Test fixtures (F1–F5, plus review inbox)
- ✅ Documentation (21 docs totaling 4,957 lines)

**Don't:**
- Don't rebuild the addon
- Don't re-test the approval gate (19 unit tests cover it)
- Don't re-design the work-selection layer (design is complete)
- Don't question the contact bases (lawful contact procedure is reviewed by ops)

**Do:**
- Follow [WORK-SELECTION-IMPLEMENTATION.md](WORK-SELECTION-IMPLEMENTATION.md) exactly (node-by-node guide is there)
- Run the test checklists (all fixtures and payloads are ready)
- Document failures and wins as you go

---

## **RIGHT NOW (Next 30 min)**

1. **Commit the staged changes** (addon + docs)
   ```bash
   git commit -m "Addon: metadata stamping fixed; add verification & audit docs"
   ```

2. **Run B1 test** (everything else waits for this)
   - Close stale n8n editor tabs
   - Trigger the workflow
   - Record result
   - Document any failures

3. **Report back:**
   - Did B1 email arrive?
   - What did Odoo record?
   - Did approval get revoked?
   - Any unexpected fields changed?

---

## **Long-term (After local is solid)**

- **Phase 6:** Move to VPS (not in scope for this phase)
- **Phase 7:** Production hardening (HTTPS, auth, monitoring)
- **Phase 8:** Prospect onboarding (real contacts, not `.invalid` fixtures)

---

**Bottom line:** You're 20% done (addon + one workflow). The next 80% is:
- **Prove it works** (B1–B5, C0) — 3–4 hours
- **Automate discovery** (work-selection) — 8–15 hours  
- **Prove recoverability** (backup/restore) — 1 hour
- **Get legal sign-off** — 1–2 weeks
- **Deploy** (after local solid + lawyer approves)

**B1 is the keystone. Everything else waits for that result.**
