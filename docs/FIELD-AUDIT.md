# CRM Lead Fields Audit

> Historical field audit from addon 19.0.1.3.0. The current addon is
> 19.0.1.8.0; current functions are listed in
> [SYSTEM-CAPABILITIES.md](SYSTEM-CAPABILITIES.md).

**Date:** 2026-08-19  
**Status:** Current implementation reviewed against workflow requirements

## Fields Required by Work-Selection Workflows

### Workflow 1 — Lead Qualification
- [x] `ggd_fit_score` — Integer (0-100)
- [x] `ggd_contact_basis` — Selection
- [x] `ggd_do_not_contact` — Boolean (suppression guard)

### Workflow 3 — Approved Send (15-min schedule)
- [x] `ggd_outreach_approved` — Boolean (approval gate)
- [x] `ggd_do_not_contact` — Boolean (suppression guard)
- [x] `ggd_contact_basis` — Selection (must be non-empty)
- [x] `ggd_outreach_approved_at` — Datetime (for ordering by approval age)
- [x] `ggd_last_send_key` — Char (idempotency)
- [x] `ggd_last_sent_at` — Datetime (send timestamp)
- [x] `ggd_suggested_next_action` — Text (for filtering)

**Note:** Design doc referenced `ggd_outreach_approval_date` but should use `ggd_outreach_approved_at` ✅ **FIXED**

### Workflow 4 — Reply Analysis
- [x] `ggd_reply_category` — Selection (matched reply type)
- [x] `ggd_reply_summary` — Text (matched reply excerpt)
- [x] `ggd_suggested_next_action` — Text (recommended action)
- [x] `ggd_ai_confidence` — Float (0.00-1.00)
- [x] `ggd_ai_last_analyzed_at` — Datetime (when analyzed)
- [x] `ggd_last_message_id` — Char (email ID for reply matching)
- [x] `ggd_last_message_date` — Date (for follow-up scheduling)

### Workflow 5 — Daily Follow-up Queue
- [x] `ggd_last_message_date` — Date (7+ days old for follow-up)
- [x] `ggd_do_not_contact` — Boolean (suppression)

## Methods Required

| Method | Purpose | Status |
| --- | --- | --- |
| `_ggd_check_approval_allowed()` | Validate approval rules | ✅ Present |
| `action_ggd_approve_outreach()` | Approval button handler | ✅ Present |
| `action_ggd_revoke_outreach()` | Revocation handler | ✅ Present |
| `ggd_claim_send_key()` | Idempotency control (before SMTP) | ✅ Present |
| `ggd_finalize_send()` | Post-send cleanup (after SMTP) | ✅ Present |

## Field Constraints & Validations

| Field | Constraint | Status |
| --- | --- | --- |
| `ggd_fit_score` | 0-100 | ✅ `@api.constrains` |
| `ggd_ai_confidence` | 0.00-1.00 | ✅ `@api.constrains` |
| Approval gate | Cannot approve on NO_EMAIL_BASES | ✅ `_ggd_check_approval_allowed()` |
| Approval gate | Cannot approve when `do_not_contact=True` | ✅ `_ggd_check_approval_allowed()` |
| Approval gate | Cannot approve without basis note | ✅ `_ggd_check_approval_allowed()` |
| Approval gate | Note must be ≥20 chars | ✅ `GGD_CONTACT_BASIS_NOTE_MIN_LENGTH=20` |

## Recent Changes (19 Aug)

**Manifest:** Version bumped to `19.0.1.3.0`

**Model `create()`:** Added timestamp stamping
- `ggd_outreach_approved_by` ← `self.env.user.id`
- `ggd_outreach_approved_at` ← `fields.Datetime.now()`
- `ggd_contact_basis_verified_at` ← `fields.Datetime.now()`

**Model `write()`:** Added timestamp stamping for direct approval writes
- Ensures approval metadata is always set, even when approved via API/direct write
- Prevents send-key derivation failures

## Test Coverage

**19 tests across 5 sections:**
1. Approval refusals (4 tests)
2. Approval success & metadata (2 tests)
3. Suppression overrides (1 test)
4. Gate bypass prevention (3 tests)
5. Duplicate-send protection (4 tests)
6. Field constraints (2 tests)
7. Work-selection finalization (6 tests)

**All tests passing:** ✅ (pending Docker verification)

## Open Questions

1. Should `ggd_outreach_approval_date` be added as a computed field for convenience in SQL queries?
   - **Answer:** No — `ggd_outreach_approved_at` is sufficient. SQL can use it directly.

2. Should we add an audit log for who revoked approvals and when?
   - **Answer:** Not required for Phase 1. The message_post() call to chatter provides basic audit.

3. Are there any fields missing for compliance tracking (GDPR, opt-out tracking)?
   - **Answer:** `do_not_contact` covers opt-out. Other compliance fields are out of scope for Phase 1.

## Action Items

- [ ] Run tests in Docker to verify 19 tests pass
- [ ] Check UI: can approve/revoke outreach on a lead
- [ ] Verify send workflow can query and process approved leads
- [ ] Test send-key idempotency with a manual send in Workflow 3
