# Section C: Backup & Restore Drill (Ready to Execute)

**Status:** Ready for execution. 18 August 2026.

This document provides step-by-step procedures for backing up and restoring the system to prove disaster recovery works. Run after Section B.

---

## **Pre-Drill Checklist**

- [ ] Section B tests complete and passing
- [ ] Odoo is running and healthy
- [ ] n8n is running and healthy
- [ ] Docker Desktop is available
- [ ] ~10 GB free disk space (backup + isolated test environment)
- [ ] Terminal access available for docker commands
- [ ] External storage available (USB drive, cloud, encrypted folder)

---

## **Phase 1: Create Fresh Backup (10 min)**

### **Step 1: Backup Script**

```bash
./scripts/backup.sh
```

**What it does:**
- Dumps Odoo database (PostgreSQL)
- Exports n8n database
- Archives filestore and attachments
- Creates timestamped archive in `backups/`

**Expected output:**
```
Backup created at backups/20260818T***Z
Copy it to encrypted storage outside this computer.
```

**Record backup timestamp:** ________________________

### **Step 2: Verify Backup Contents**

```bash
ls -lh backups/20260818T*
```

**Should show:**
- Odoo database SQL dump (~50 MB)
- n8n database dump (~10 MB)
- Filestore archive (~500 MB)
- Total: ~600 MB

**Backup size:** ________________________ MB

### **Step 3: Copy to External Storage**

```bash
# Copy to USB or cloud
cp backups/20260818T*.tar.gz /path/to/external/storage/
```

**Or use:**
```bash
# Encrypted archive to home directory
gpg --symmetric --cipher-algo AES256 backups/20260818T*.tar.gz
# Creates .tar.gz.gpg file
```

**External storage path:** ________________________
**Encrypted?** ☐ YES ☐ NO

---

## **Phase 2: Isolated Restore Test (30 min)**

This tests that you can restore from backup in a clean environment (simulates emergency recovery).

### **Step 1: Create Isolated Docker Project**

Create a new folder for the isolated test:

```bash
mkdir ~/ggd-restore-test
cd ~/ggd-restore-test
cp /path/to/GGD-Sales-System/compose.yaml .
cp /path/to/GGD-Sales-System/.env .
```

**Important:** Modify `.env` for isolated names:

```bash
# Change these to avoid conflicts with running system:
COMPOSE_PROJECT_NAME=ggd-sales-test
ODOO_DB_NAME=ggd_restore_test
N8N_DB_NAME=n8n_restore_test
ODOO_LOCAL_PORT=8070  # different from 8069
```

**Isolated project path:** ________________________

### **Step 2: Start Fresh Containers**

```bash
cd ~/ggd-restore-test
docker compose up -d
```

**Wait** ~30 seconds for containers to initialize.

**Verify they're running:**

```bash
docker compose ps
```

Should show all containers HEALTHY or running.

**Status:** ________________________

### **Step 3: Extract Backup to Isolated Environment**

**Find the backup file:**

```bash
ls -lh ~/backups/20260818T*.tar.gz
```

**Extract it:**

```bash
cd ~/ggd-restore-test
tar -xzf ~/backups/20260818T*.tar.gz
```

This extracts the SQL dumps and filestore data.

**Extracted files:**

```bash
ls -la
# Should show: odoo-dump.sql, n8n-dump.sql, filestore/ directories
```

### **Step 4: Restore Odoo Database**

```bash
docker compose exec -T odoo-db psql -U odoo odoo_restore_test < odoo-dump.sql
```

**Expected:** No errors, may take 1-2 minutes.

**Odoo restore status:** ☐ SUCCESS ☐ FAILED (error: __________________)

### **Step 5: Restore n8n Database**

```bash
docker compose exec -T n8n-db psql -U n8n n8n_restore_test < n8n-dump.sql
```

**Expected:** No errors.

**n8n restore status:** ☐ SUCCESS ☐ FAILED (error: __________________)

### **Step 6: Restore Filestore**

```bash
docker compose exec -u root odoo bash -c "cp -r filestore/* /var/lib/odoo/"
```

**Expected:** Files copied silently (no output = success).

### **Step 7: Restart Containers**

```bash
docker compose restart odoo n8n
```

**Wait** ~30 seconds.

```bash
docker compose ps
```

**Should show:** Both HEALTHY.

---

## **Phase 3: Verification (15 min)**

### **Step 1: Odoo Accessibility**

Open browser: **http://localhost:8070** (isolated port, different from production)

**Can you access Odoo?** ☐ YES ☐ NO

If yes:
- [ ] Login works (use original credentials from .env)
- [ ] CRM data present (check for test records)
- [ ] Workflows visible (check workflow list)

**Odoo status:** ________________________

### **Step 2: n8n Accessibility**

Open browser: **http://localhost:5678** (same port, but new container)

**Can you access n8n?** ☐ YES ☐ NO

If yes:
- [ ] Workflows present (GGD 03, GGD 04, GGD 05, etc. visible)
- [ ] Credentials present (check Credentials page)
  - [ ] Odoo credential exists
  - [ ] SMTP credential exists
  - [ ] LLM credential exists
- [ ] GGD 99 (error handler) present

**n8n status:** ________________________

### **Step 3: Test Workflow Execution**

Run a simple workflow in restored environment:

1. **In n8n (isolated):**
   - Open GGD 99 (error handler)
   - Click "Test workflow"
   - Should complete without error

2. **Check result:**
   - [ ] Execution succeeded (green)
   - [ ] Can access error handler
   - [ ] Workflow logic intact

**Workflow test status:** ________________________

### **Step 4: Verify Data Integrity**

**In Odoo (isolated):**

1. Open a test record from production (e.g., WS-F1)
2. Verify fields match production:
   - Record ID: ________________________ (same as production)
   - Name: ________________________ (matches)
   - Approval status: ________________________ (matches)

**Data integrity:** ☐ MATCHES PRODUCTION ☐ DISCREPANCIES

---

## **Phase 4: Cleanup (10 min)**

### **Step 1: Stop Isolated Environment**

```bash
cd ~/ggd-restore-test
docker compose down
```

**Expected:** All containers stopped.

### **Step 2: Delete Test Data (OPTIONAL)**

If restore verified successfully:

```bash
# Keep the restore test folder for reference, or delete:
# rm -rf ~/ggd-restore-test

# Delete extracted SQL dumps:
# rm ~/backups/*-dump.sql
```

### **Step 3: Verify Production Still Running**

Back to main project:

```bash
cd /path/to/GGD-Sales-System
docker compose ps
```

**Should show:** Production containers still running (8069, 5678 ports).

**Production status:** ☐ HEALTHY ☐ ISSUES (describe: __________________)

---

## **Backup & Restore Summary**

| Phase | Status | Time |
| --- | --- | --- |
| Backup creation | ☐ PASS | ______ |
| External copy | ☐ PASS | ______ |
| Isolated setup | ☐ PASS | ______ |
| Odoo restore | ☐ PASS | ______ |
| n8n restore | ☐ PASS | ______ |
| Odoo verification | ☐ PASS | ______ |
| n8n verification | ☐ PASS | ______ |
| Data integrity | ☐ PASS | ______ |
| Production intact | ☐ PASS | ______ |

**All phases pass?** ☐ YES → Ready for sign-off
**Issues found?** ☐ YES → Document below

---

## **Troubleshooting**

### **Backup creation fails**

```bash
# Check disk space
df -h

# Check backup script permissions
ls -la scripts/backup.sh

# Run with verbose output
bash -x scripts/backup.sh
```

### **Restored Odoo won't start**

```bash
# Check Odoo logs
docker compose -f ~/ggd-restore-test/compose.yaml logs odoo --tail 50

# Verify database restore completed
docker compose -f ~/ggd-restore-test/compose.yaml exec odoo-db psql -U odoo -d ggd_restore_test -c "SELECT count(*) FROM crm_lead;"
```

### **Restored n8n has no workflows**

```bash
# Verify database restore
docker compose -f ~/ggd-restore-test/compose.yaml exec n8n-db psql -U n8n -d n8n_restore_test -c "SELECT count(*) FROM workflow;"
```

### **Credentials don't work in restored n8n**

n8n encryption keys may not match. The restored n8n instance uses a different encryption key than production, so credentials may be unreadable. This is expected and acceptable — it proves the structure is intact but emphasizes the importance of:
1. Keeping `.env` (N8N_ENCRYPTION_KEY) in a password manager
2. Testing restore on a fresh machine with the same key

---

## **Sign-Off**

Backup & Restore Drill complete?

**Date:** ________________________
**Tester:** ________________________
**Result:** ☐ PASS ☐ FAIL
**Issues:** ________________________

**External backup location:** ________________________
**Encryption:** ☐ YES ☐ NO

**Next steps:**
- [ ] Copy external backup to secure storage (off-computer)
- [ ] Save .env encryption key in password manager
- [ ] Document recovery procedure for incident response

---

## **Recovery Procedure (For Reference)**

If production fails and you need to recover:

1. Deploy fresh system on new hardware (same specs, OS, Docker version)
2. Copy backup from external storage to new machine
3. Follow **Phase 2** and **Phase 3** procedures (restore + verify)
4. Point DNS/traffic to new instance
5. Verify all workflows, data, and user access

**Estimated recovery time:** 30–60 minutes (backup extraction + restore + verification)

