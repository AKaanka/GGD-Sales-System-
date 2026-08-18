# C0 Proof: Error Handler Fires (2-Minute Test)

**Status:** Ready to run. 18 August 2026.

This test answers one critical question: **Does n8n's error handler actually fire for scheduled/automatic executions?**

The context: All workflows here are currently manual-only. n8n may not invoke error handlers for manual executions — only for scheduled runs. We need to know if the error handler works when it matters.

**Outcome:**
- ✅ **Error handler works** → C1, C2, B5, and A8 can proceed with confidence
- ❌ **Error handler broken** → This is a critical blocker; sign-off is impossible

---

## The Test Workflow: GGD 98t

This test workflow is extremely simple:
- **One schedule trigger:** Runs every 1 minute
- **One code node:** Throws an error immediately
- **Error handler:** Set to GGD 99 (shared error handler)
- **Credentials:** None (safe to run repeatedly)
- **Side effects:** None (no writes, no emails, no reads)

**Important:** This workflow will be deleted after the test.

---

## Step-by-Step Execution

### Pre-Test (Record baseline)

1. Open n8n at http://localhost:5678
2. Find and open **GGD 99** (Shared Error Handler)
3. Click **Executions** tab
4. **Record the most recent execution ID and timestamp:**
   - Latest execution ID: ________________________
   - Timestamp: ________________________
   - Note: If empty, that's okay; we're looking for NEW executions below

### Run Test (90 seconds)

1. Find **GGD 98t** (Error Handler Proof)
   - Status should show: **INACTIVE**
   - If active, someone left it running — deactivate first
2. Click the toggle to **ACTIVATE** it
   - Status changes to: **ACTIVE**
3. **Set a timer for 90 seconds** (or wait for ~2 schedule cycles)
   - The workflow has a 1-minute schedule, so expect execution within 60 seconds
   - We wait 90 to ensure at least one complete cycle
4. **After 90 seconds, immediately click toggle to DEACTIVATE** it
   - Status changes back to: **INACTIVE**
   - **Do NOT skip this step.** This is the only untested workflow and should not stay active.

### Check Results (Record findings)

1. Go back to **GGD 99** (Shared Error Handler)
2. Click **Executions** tab
3. Look for **NEW execution after the timestamp you recorded earlier**

**Result A: New execution appeared** ✅

```
Latest execution ID: ________________________ (NEW since pre-test)
Timestamp: ________________________
Status: ✅ SUCCESS — Error handler fires for scheduled runs
Conclusion: C1, C2, B5, and A8 can proceed
```

Open the execution and verify:
- [ ] Execution body contains workflow name ("GGD 98t - error handler proof")
- [ ] Execution body contains error summary (something like "ReferenceError: intentional error")
- [ ] Execution body DOES NOT contain API keys, credentials, or passwords
- [ ] Record the execution ID: ________________________

**Result B: No new execution appeared** ❌

```
Latest execution ID: ________________________ (UNCHANGED from pre-test)
Timestamp: ________________________
Status: ❌ FAILED — Error handler does not fire for scheduled runs
Conclusion: This is a critical blocker for C1, C2, B5, A8, and sign-off
Next step: Investigate n8n error handler configuration or n8n logs
```

---

## What Happens If Test Fails

If no new execution appears in GGD 99:

1. **Check GGD 98t execution history** (the test workflow):
   - Go to GGD 98t
   - Click Executions
   - Does it show any runs? (It should show ~1-2 runs in the last 90 seconds)
   - If no runs appear, the schedule trigger didn't fire

2. **Check n8n activity log/dashboard** for errors

3. **Investigate workflow error settings:**
   - Open GGD 04 (main workflow)
   - Check Error workflow setting (should be "GGD 99")
   - Check the same on GGD 98t

4. **Check n8n logs:**
   ```bash
   docker compose logs n8n --tail 100 | grep -i error
   ```

5. **Document the finding** and block on it before proceeding with C1, C2, B5

---

## What Happens If Test Passes

If a new execution appears in GGD 99:

1. ✅ Record the execution ID and timestamp above
2. ✅ Verify no secrets leaked in the execution body (C2 evidence)
3. ✅ Delete GGD 98t:
   - Right-click GGD 98t in workflow list
   - Select "Delete"
   - Confirm deletion
4. ✅ Update PROJECT-STATUS.md:
   ```markdown
   | Error handling | C0 proof passed 18 August. Error handler fires for scheduled executions. |
   ```
5. ✅ Proceed with C1, C2, B5, and A8 tests

---

## Cleanup

**After test completes (whether pass or fail):**

1. [ ] Verify GGD 98t is DEACTIVATED
2. [ ] Delete GGD 98t from workflow list
3. [ ] Verify GGD 99 is still ACTIVE (it stays active)
4. [ ] Check GGD 99 execution history for your test run

---

## Sign-Off

**C0 Proof Status:** ☐ PASS ☐ FAIL ☐ INCONCLUSIVE

**Test Date:** ________________________

**Test Executed By:** ________________________

**Findings:** 

_________________________________________________________________

_________________________________________________________________

**Next Action:** 

- If PASS: Proceed to C1, C2, B5, A8 testing
- If FAIL: Investigate n8n error handler configuration; block on resolution

---

## Reference: What C0 Actually Tests

From the QA-TEST-PACK.md findings:

> "The wiring is correct: GGD 04, 04c, 04t and 03 all reference `xMbI9hyKnfim5M1q` as their error workflow, and GGD 99 is active. But GGD 99's most recent execution is #84, from 16 August, while 18 August produced several genuine failures — two Anthropic timeouts and one node error on 04c. None of them produced an error-handler execution.

> The evidence points to n8n not invoking the error workflow for **manual** executions. Every workflow here is inactive and manual-only, by design. So the entire error-handling layer has never engaged for a real failure, and cannot under the conditions this pack currently uses."

**This test proves whether that limitation applies:**
- If error handler fires on scheduled run → it works, manual-only is the issue
- If error handler does NOT fire on scheduled run → it's broken outright

---

## Questions?

Refer to:
- [QA-TEST-PACK.md](QA-TEST-PACK.md) Section C0 for context
- [PROJECT-STATUS.md](PROJECT-STATUS.md) for blocker status

If the test is inconclusive or GGD 98t doesn't exist in your n8n instance, you may need to create it. Contact the project lead for the workflow definition.

