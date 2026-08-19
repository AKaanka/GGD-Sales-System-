# Addon Verification Checklist

**Date:** 2026-08-19  
**Owner:** You  
**Goal:** Validate the CRM addon is production-ready before workflow integration

---

## ✅ Completed (Claude)

- [x] Fixed field naming in WORK-SELECTION-IMPLEMENTATION.md
- [x] Created test runner script (`scripts/run-addon-tests.sh`)
- [x] Audited all fields against workflow requirements
- [x] Verified all 5 required methods are implemented
- [x] Reviewed test coverage (19 tests documented)
- [x] Identified recent changes (metadata stamping in create/write)

---

## ⏳ YOUR TASKS (Please complete and check off)

### Phase 1: Verify Docker Environment (5 min)

- [ ] **Check services are running**
  ```bash
  docker compose ps
  ```
  Expected: `odoo` and `n8n` show "Up"

- [ ] **Verify Odoo is accessible**
  - Open `http://localhost:8069`
  - Login with your Odoo credentials
  - Check you can see the CRM app and Leads module

- [ ] **Verify n8n is accessible** (optional at this stage)
  - Open `http://localhost:5678`
  - Check that workflows are listed

### Phase 2: Run Addon Tests (10 min)

- [ ] **Make test script executable and run it**
  ```bash
  cd "/Users/kaan/Desktop/GGD -Sales-System "
  chmod +x scripts/run-addon-tests.sh
  ./scripts/run-addon-tests.sh
  ```

- [ ] **Record the result**
  ```
  Expected output: "19 tests passed"
  Actual output:  ________________
  Date/time:      ________________
  ```

- [ ] **If tests FAILED:** Note which ones and check if they are:
  - Pre-existing failures (not our responsibility now)
  - New failures caused by recent changes (we need to debug)
  - Environment issues (Odoo not running)

### Phase 3: Test Approval Flow in UI (10 min)

- [ ] **Create/find a test lead**
  - Go to CRM → Leads
  - If no test lead exists, create one:
    - Name: "Test Lead — Approval Flow"
    - Email: `approval-test@ggd-qa.invalid`
    - Save
  - Note the ID: _____ (from URL, e.g., /crm/lead/123)

- [ ] **Fill contact basis**
  - Contact basis: Select "Prior express consent — opt-in on file"
  - Contact-basis note: Type: "Opted in via website form on 2026-08-15"
  - Save

- [ ] **Click "Approve Outreach" button**
  - Expected: Button is visible and enabled
  - After click: Page reloads
  - Check the following fields now show values:
    - [ ] `Outreach approved` = True
    - [ ] `Approved by` = Your username
    - [ ] `Approved at` = Today's date + time (read-only)
    - [ ] `Contact basis verified at` = Today's date + time (read-only)

- [ ] **Test the revoke button**
  - Click "Revoke Approval" button
  - Check that:
    - [ ] `Outreach approved` = False
    - [ ] `Approved by` = (empty)
    - [ ] `Approved at` = (empty)
    - [ ] `Contact basis verified at` = (empty)

- [ ] **Test approval with do_not_contact flag**
  - Click "Approve Outreach" again to re-approve the lead
  - Check `Do not contact` checkbox
  - Save
  - Check that:
    - [ ] `Outreach approved` auto-reverted to False
    - [ ] `Approved by` is cleared
    - [ ] All approval metadata cleared

- [ ] **Record completion**
  ```
  Test lead ID:       ________________
  All steps passed:   [ ] Yes  [ ] No
  Issues found:       ________________
  ```

### Phase 4: Verify Send-Key Claim Method (5 min, optional but recommended)

- [ ] **Open Odoo shell** (for technical testing)
  ```bash
  docker compose exec odoo odoo shell -d ggd
  ```

- [ ] **Run a quick test of the send-key method**
  ```python
  lead = env['crm.lead'].browse(4)  # Use a test lead ID
  
  # Claim a send key
  result1 = lead.ggd_claim_send_key("test-send-1")
  print(f"First claim: {result1}")  # Should be True
  
  # Try to claim the same key again
  result2 = lead.ggd_claim_send_key("test-send-1")
  print(f"Second claim: {result2}")  # Should be False
  
  # Claim a different key
  result3 = lead.ggd_claim_send_key("test-send-2")
  print(f"New key claim: {result3}")  # Should be True
  
  exit()
  ```

- [ ] **Record results**
  ```
  First claim returned:   [ ] True   [ ] False
  Second claim returned:  [ ] False  [ ] True (ERROR!)
  New key claim returned: [ ] True   [ ] False (ERROR!)
  
  All correct: [ ] Yes  [ ] No
  ```

### Phase 5: Final Review (5 min)

- [ ] **Check no secrets were exposed** in console output
- [ ] **Verify all changes are git-staged and ready to commit**
  ```bash
  git status
  ```
  You should see:
  - Modified: docs/WORK-SELECTION-IMPLEMENTATION.md
  - Modified: odoo/addons/ggd_crm/__manifest__.py
  - Modified: odoo/addons/ggd_crm/models/crm_lead.py
  - Modified: odoo/addons/ggd_crm/tests/test_crm_lead.py
  - New: docs/FIELD-AUDIT.md
  - New: docs/ADDON-WORK-SUMMARY.md
  - New: scripts/run-addon-tests.sh
  - (This checklist file)

- [ ] **Commit the changes**
  ```bash
  git add -A docs/ odoo/addons/ggd_crm/ scripts/
  git commit -m "Addon: stamp approval metadata; fix WORK-SELECTION field reference; add test runner and audit"
  ```

---

## Sign-Off

When all sections are complete:

```
Verified by:          ________________
Date:                 ________________
All tests passed:     [ ] Yes  [ ] No
UI approval works:    [ ] Yes  [ ] No
Send-key method OK:   [ ] Yes  [ ] No (optional)
Ready for workflow 3: [ ] Yes  [ ] No
```

If everything is green, the addon is ready for workflow 3 (Approved Send) implementation.

---

## Troubleshooting

### "Tests failed" 
→ Post the error message and I can help debug.

### "Approve button not visible"
→ The lead may already be approved, or the contact basis might be invalid. Check:
- Is `Do not contact` checked? (if yes, button won't show)
- Is `Contact basis` empty? (if yes, can't approve)
- Try a fresh lead with valid data.

### "Odoo not accessible"
→ Run `docker compose ps` and `docker compose logs odoo | tail -50` to see errors.

### "Can't run test script"
→ Check file permissions: `ls -la scripts/run-addon-tests.sh`  
→ Should show `rwx------` or `rwxr-xr-x`

---

*Once complete, report back and we'll move to Workflow 3 implementation in n8n.*
