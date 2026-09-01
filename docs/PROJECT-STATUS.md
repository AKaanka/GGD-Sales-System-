# Project Status — 27 August 2026 (Gate 3 step 8 closed 1 September, see below)

## Current verified state

This section supersedes the older dated narrative retained below as an audit
history.

The current repository build and local installation have passed Gates 0–2 and
all of Gate 3, including step 8 (closed 1 September — see the note below the
27 August evidence):

- Odoo addon `19.0.1.8.0` stores sourced qualification, an immutable reviewed
  draft/version, the human approval attached to that version, a deterministic
  send claim, complete SMTP audit data, replies, bounces, response drafts, and
  deduplicated follow-up activities.
- Inactive, reproducible n8n imports now exist for Workflows 1–5 and the shared
  error handler under `workflows/`.
- Workflow 3 no longer drafts after approval. It sends only the exact stored
  and approved subject/body version.
- Workflow 4 includes IMAP reply intake and bounce handling. Hard bounces and
  unsubscribe replies suppress further contact.
- Workflow 5 runs at 08:30 Europe/Berlin on weekdays and calls an Odoo method
  that atomically deduplicates the review activity for each confirmed send.
- Odoo database `ggd` confirms addon `19.0.1.8.0` is installed. The live addon
  run completed with 0 failures and 0 errors across all 108 tests.
- Static project validation reports 26/26 current workflow checks and 19/19
  legacy reply-matcher regressions passing.
- The six current exports were imported into n8n 2.34.6 in number order. All
  are inactive and Workflows 01–05 reference GGD-00 as their error workflow.

### Gate 3 results — 27 August 2026

Gate 3 is complete except step 8. All testing used fictional `.invalid`
fixtures (FX1–FX7, Odoo records 430–437) and no email was sent.

| Step | What it proves | Result |
| --- | --- | --- |
| 1 | W1 qualifies a lead and never approves outreach | PASS |
| 2 | W2 stores one versioned draft and stops for human review | PASS |
| 3 | Kaan reviews the exact draft; no email sent | PASS |
| 4 | W4 handles matched, unmatched, ambiguous, unsubscribe and bounce | PASS — all six scenarios |
| 5 | W5 creates one deduplicated follow-up activity | PASS |
| 6 | Bounce and unsubscribe suppression recorded durably in Odoo | PASS |
| 8 | Shared error handler catches a real failure | OUTSTANDING |
| 9 | Live n8n graphs match the tracked exports | PASS — exit 0 |

Step 4/6 detail: FX2 matched by sender email; FX5 matched by Message-ID; an
unmatched inbound created review record 810 and replaying the same email
created no second record; an ambiguous sender created review record 811 and
left both FX6A and FX6B untouched rather than guessing; an unsubscribe set
FX2 to `do_not_contact`; and a hard bounce set FX5 to bounced with
`do_not_contact` and a delivery review, matched via `Original-Message-ID`
pulled from the DSN body with no `In-Reply-To` header present.

Step 9 detail: `tests/workflows/compare-live-exports.js` compares each live
export against its committed file — node set, type, typeVersion, disabled flag,
full parameters path by path, credential slot names, and the connection map.
The 27 August run reported GRAPH 0, UNEXPLAINED 0, PIN 0, CONFIRMED-OK 2, exit
code 0. Ten differences are classified as expected (eight n8n default-omissions
on export, one trailing-newline difference in a `jsCode` block, and the
placeholder-bound fields below).

Placeholder-bound fields are class CONFIRM, not auto-approved: the tracked
files carry `REPLACE_WITH_*` by design so they can be shared, and the live
value is printed and blocks the run until a human reads it. Both currently bind
to a Kaan-owned address, read and confirmed on 27 August. Confirmed values are
stored as SHA-256 in `tests/workflows/confirmed-bindings.json`, so the check can
pass on repeat runs while any later change fails loudly with the new value
printed. An earlier version of the comparator treated these as silently
expected, and a negative test that rewrote the Gate 4 recipient allowlist to an
attacker address passed clean. Do not weaken this.

Step 8 — DONE, 1 September. A fresh fixture (Odoo lead 812, an `.invalid`
source URL) was used to force a genuine scheduled (non-CLI, non-manual)
failure in GGD-01 at the "Fetch approved public company page" node; GGD-00
caught it, sanitized it, correctly recorded `send_may_have_occurred: false`,
and logged it both in n8n and via Odoo's `ggd_record_automation_error`
(executions #532–#535). GGD-01 was then unpublished (confirmed via the
Executions list) and its schedule reverted to Hours/1 to match the tracked
export; fixture 812 was archived. Gate 3 is now fully complete. Full
step-by-step evidence is in NEXT-ACTIONS.txt.

Open and cosmetic: 17 credential slot NAME mismatches. Live n8n kept its own
defaults (`Header Auth account`, `SMTP account`, `IMAP account`) rather than the
documented names (`Odoo JSON-2 bearer token`, `Zoho SMTP`, `Zoho IMAP`). The
bindings authenticate correctly; only the names disagree with the
documentation. Renaming the three credentials in the n8n UI clears all 17.

### Gate 2 import evidence

| Workflow | Stored n8n workflow ID | Type/version | Saved nodes | Saved connections |
| --- | --- | --- | --- | --- |
| GGD-00 | `G00ERR20260826A` | PASS | PASS | PASS |
| GGD-01 | `G01QUAL20260826` | PASS | PASS | PASS |
| GGD-02 | `G02DRFT20260826` | PASS | PASS | PASS |
| GGD-03 | `G03SEND20260826` | PASS | PASS | PASS |
| GGD-04 | `G04RPLY20260826` | PASS | PASS | PASS |
| GGD-05 | `G05FOLW20260826` | PASS | PASS | PASS |

These are the actual stored workflow IDs returned by n8n's
`export:workflow` command, not temporary import labels.

The type/version check compared every saved node against the live n8n 2.34.6
node registry; no unknown type or unsupported version was found. After import,
n8n's own `export:workflow` command re-read each stored workflow. Its node set
and connections matched the tracked export, all six stored `active: false`,
and Workflows 01–05 stored error workflow ID `G00ERR20260826A`.

Before Gate 3, GGD-03 gained the temporary Gate 4 recipient allowlist. Its true
branch reaches the send-key claim, while its false branch throws a visible
error before a claim can be consumed. The tracked export retains only
`REPLACE_WITH_KAAN_TEST_RECIPIENT`; the real Kaan-owned address must be entered
locally in n8n and must not be committed. The updated stored workflow was
re-exported as `G03SEND20260826`: it remained inactive, retained GGD-00 as its
error workflow, and its 15-node graph and connections matched the tracked
export.

Claude Code fixed the FX5 send-key shape defect, and the orchestrator then ran
`scripts/create-gate3-fixtures.sh` successfully. Seven fictional `.invalid`
fixtures were created as Odoo records 430–436; the exact summary is recorded
in `docs/handoffs/CLAUDE-CODE.md`. Gate 3 workflow execution remains unstarted
and manual-trigger only.

### Gate 3 preflight record — 26 August 2026

Retained as history. The preflight below predates the 27 August results above;
where the two disagree, the section above is current.

| Step | Evidence | Result |
| --- | --- | --- |
| W1 selector before Step 1 | The exact tracked domain initially matched FX1 (ID 430) and stray test record `GGD Test – Anatolia Packaging` (ID 2). ID 2 was parked with `ggd_automation_needs_review = true`; the exact selector was rerun and then matched only FX1. | PASS |
| W2 selector before Step 3 | The exact tracked domain matched only FX2 (ID 431). | PASS |
| W1 error-path execution | Live W1 remains inactive, but both Odoo HTTP nodes still reference `REPLACE_WITH_ODOO_JSON2_CREDENTIAL`. The available n8n editor requires Kaan to sign in. Execution was not attempted because it could not authenticate to Odoo. | BLOCKED: KAAN CREDENTIAL BINDING |

Decision 1 is approved for `https://www.germanygrowthdesk.com`, and
Decision 2 approves temporary W1 activation only after Gate 3 Steps 1–7 are
complete and evidenced. Claude Code added FX7 to the idempotent fixture script;
the orchestrator reran it and created FX7 as Odoo ID 437. Gate 3 remains paused
until Kaan confirms the full n8n credential-binding pass.

Standing credential order: never export, read, copy, or query n8n credential
material or its database table. Credential validity is verified only when a
bound workflow node authenticates successfully during an authorized run.

#### Pre-Gate 3 workflow-reference audit

This audit used `n8n export:workflow` only. IDs below are node references from
workflow definitions; no credential record or credential material was read.
All six workflows were inactive.

| Workflow | Credential node | Exported reference |
| --- | --- | --- |
| GGD-00 | Record concise error in Odoo | PLACEHOLDER — `REPLACE_WITH_ODOO_JSON2_CREDENTIAL` |
| GGD-01 | Select unqualified opportunities | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-01 | Anthropic qualification model | BOUND — `NE8L3f7kbmNEzLMY` |
| GGD-01 | Record qualification in Odoo | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-02 | Select qualified leads without drafts | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-02 | Anthropic drafting model | BOUND — `NE8L3f7kbmNEzLMY` |
| GGD-02 | Store immutable draft for human approval | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-03 | Select approved reviewed drafts | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-03 | Claim send key before SMTP | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-03 | Send exact reviewed draft via Zoho | BOUND — `C3sp9peOXU3kpGft` |
| GGD-03 | Finalize complete send audit in Odoo | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-03 | Record uncertain send for manual recovery | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-04 | Zoho IMAP inbox | BOUND — `hnoyVj7AN6kpoTQk` |
| GGD-04 | Match in Odoo by reply ID then sender | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-04 | Queue unmatched inbound for Odoo review | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-04 | Record matched bounce in Odoo | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-04 | Anthropic reply model | BOUND — `NE8L3f7kbmNEzLMY` |
| GGD-04 | Record reply and response draft in Odoo | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-05 | Select stale contacted opportunities | BOUND — `CXGIrrsgmgNhPGXQ` |
| GGD-05 | Anthropic follow-up model | BOUND — `NE8L3f7kbmNEzLMY` |
| GGD-05 | Create one deduplicated Odoo review activity | BOUND — `CXGIrrsgmgNhPGXQ` |

The refreshed audit found one remaining incomplete binding: GGD-00's Odoo
error-record node. Kaan's known pre-Gate-3 manual GGD-05 run is recorded separately
from formal Gate 3 evidence: its selector authenticated successfully to Odoo
and reached `Draft manual follow-up`, then failed with `resource not found`
because all four Anthropic nodes still pin retired model
`claude-sonnet-4-20250514`. The run did not reach the Odoo activity-creation
node and is not counted as a Gate 3 W5 result.

The live Anthropic dropdown listed `Claude Sonnet 5` as the newest Sonnet.
GGD-01, GGD-02, GGD-04, and GGD-05 now all save exact model ID
`claude-sonnet-5`; their tracked exports match. A regression test requires one
identical non-retired model across all four exports. Validation now passes
24/24 workflow checks plus 19/19 matcher regressions. A workflow-only re-export
confirmed all six node sets and connections match the tracked files and all six
are inactive.

During the W1 editor save, n8n 2.34 treated `Publish` as activation. The
orchestrator immediately unpublished W1, but one hourly execution (ID 476,
17:00:18) fired first. It failed at `One qualification candidate per item`
with `Opportunity 430 has an invalid public source URL`; Odoo verification
showed FX1 remained pending, unapproved, and not parked. This execution is
pre-Gate-3 evidence and does not count as Step 1. The exact W1 selector still
matches only FX1, and the exact W2 selector still matches only FX2.

The authenticated REST detail URL was blocked by the in-app browser's local
security layer, so the saved-graph reread used n8n's database-backed export
command rather than claiming an API verification that did not occur. No editor
canvas was opened, avoiding the known stale-editor overwrite hazard.

No credential was changed, no imported workflow was executed or activated,
and no email was sent.

### Remaining functional acceptance

Items 1 and 2 of the original list are complete. What remains:

1. ~~Gate 3 step 8~~ — DONE, 1 September (see above).
2. Gate 4 — controlled send EXECUTED 1 September (n8n execution #550,
   1.072s). FX4 (record 433) was retargeted from its `.invalid` address to
   `kaan@germanygrowthdesk.com`, which auto-revoked its approval; Kaan
   re-approved in Odoo at 15:16:05 UTC, and GGD-03 was run manually (never
   published). Verified: `ggd_delivery_status` accepted, `ggd_draft_status`
   sent, Message-ID `<cba5013a-…@germanygrowthdesk.com>` recorded, sent
   subject and draft version `7f261a44…` unchanged, deterministic send key
   `433:7f261a44…` with the confirmed key equal to it, and approval consumed.
   A second run (#551) selected 0 candidates and sent nothing. The live
   allowlist and sender both still match their SHA-256 pins. STILL OPEN:
   Kaan's confirmation that exactly one message arrived, plus two optional
   drills (claim-level duplicate blocking, and uncertain-send recovery —
   the latter sends a real second email by design). Reply and bounce paths
   were already proven in Gate 3.
3. Gate 5: re-run validation and the 108 addon tests, then the backup and
   isolated restore drill. Before that drill, free disk space (was at 98%,
   5.9 GB of 229 GB) and account for the roughly 31 Odoo modules installed on
   27 August, which the restore has to reproduce.
4. ~~Delete the legacy August workflows~~ — DONE, 1 September. `GGD 03`
   (`OAuSsgxfMxGOFIs3`) and `GGD 03s` (`JfvdLsInvAabILwc`) were exported to
   `backups/20260901T-legacy-send-workflows/` (git-ignored, local only) from
   the 20 August database dump, which postdates both workflows' last edits,
   then archived and permanently deleted in n8n. Workflow count went 20 → 18;
   all six current workflows and all five credentials are untouched. An audit
   of the same dump confirmed these two were the ONLY legacy August workflows
   with an email-send node or SMTP credential — the remaining twelve reference
   only Odoo/Anthropic and cannot send mail.
5. Lawful-contact review before any real prospect is contacted.

The import instructions are in [workflows/README.md](../workflows/README.md).
The next single action is kept in [NEXT-ACTIONS.txt](../NEXT-ACTIONS.txt).

## Historical status and defect log — 18–20 August 2026

Supersedes the 16 August status. Detailed test evidence lives in
[QA-TEST-PACK.md](QA-TEST-PACK.md); the history of how the reply-matching design
was reached is in [QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md) and
[WORKFLOW4-MATCHING-DESIGN.md](WORKFLOW4-MATCHING-DESIGN.md).

## Plain-language summary — 18–20 August record

Retained as history. Both concerns raised below have since been addressed: the
workflows now select their own work, and the shared error handler is bound and
published, and its live proof (Gate 3 step 8) closed 1 September. See the
27 August sections above for the current position.

The local system runs, and Workflow 4 — reply analysis — is now genuinely
tested rather than assumed. Eight of the nine Section A acceptance tests pass
against the live workflow, and the testing found and fixed five real defects
along the way.

Two things should temper that. First, **no workflow selects its own work**: all
five are `manual trigger → hardcoded ID → fetch one record`. The logic that
decides *who gets contacted* does not exist yet. Second, **the shared error
handler has never actually fired**, so the entire error-handling layer is
unproven. Neither is visible from a checklist that says "workflows built" and
"error workflow assigned".

No real prospect has been contacted. All testing used fictional `.invalid`
fixtures. All workflows remain inactive and IMAP remains disabled.

## Defects found and fixed, 17–18 August

| # | Defect | Why it mattered |
| --- | --- | --- |
| 1 | Unmatched replies were dropped silently | An Odoo search returning nothing ended the run, and n8n marked it **successful**. Every manual-review safeguard was unreachable for the case that most needed it. Fixed with Always Output Data. |
| 2 | Suppression guard read an undefined field | After the matcher was moved, `ggd_do_not_contact` no longer reached the check. It evaluated falsy, so **every suppressed contact would have taken the normal path** — a safety control that looked present and did nothing. |
| 3 | No low-confidence threshold existed | Output at 0.30 confidence was written exactly like output at 0.99. Now gated at 0.7 on `If1`, defined in one place. |
| 4 | Message IDs eaten by the HTML sanitiser | Review notes lost the one identifier needed to find the original email, silently. All interpolated values are now escaped. |
| 5 | No duplicate-send protection | Nothing prevented a repeat send. A send key is now claimed **before** SMTP, so a crash cannot cause a second send. |

Defects 1 and 2 were both introduced or exposed by restructuring, and neither
produced an error. Treat "the run succeeded" as weak evidence.

## Further defects found 19 August, during Section B

| # | Defect | Why it mattered |
| --- | --- | --- |
| 6 | Outbound gate accepted any non-empty contact basis | `referral`, `other` and trade-fair-without-opt-in are never lawful for a first email. Odoo refused to *approve* them; the send workflow never checked *which* basis. Anything approved before that guard existed would still have sent. Fixed with an independent second check. |
| 7 | Send-key claim node wrote seven unrelated fields as 0 | Inherited by cloning. A successful send would have zeroed `probability`, `expected_revenue`, `ggd_fit_score` and `ggd_ai_confidence` as a side effect of an idempotency check. |
| 8 | Send-key claim node had a blank record ID | The Odoo update targeted no record, **reported success**, wrote no key — and the email sent anyway. A safety control that reported success while doing nothing. |
| 9 | Audit node referenced a node name missing its trailing period | Latent since creation; unreachable until a send actually succeeded. |
| 10 | Deactivating a workflow can silently fail | `GGD 98t` read `active: false` while still firing every minute for at least seven cycles. On an outbound workflow this would send while appearing switched off. |

Two open findings, neither yet fixed:

- **SMTP acceptance is treated as delivery.** A message accepted for an
  unroutable address marks the record as contacted; the later bounce never
  reaches the CRM. LAWFUL-CONTACT-PROCEDURE.md section 7 requires hard bounces
  to end sending, and nothing implements that.
- **n8n executes the workflow copy loaded in the browser**, not necessarily the
  saved one, and an open editor tab can re-save over API changes. Verify by
  re-reading after saving, and reload before running.

## Where each area stands

| Area | Status |
| --- | --- |
| Workflow 4, reply analysis | A1–A7 and A9 pass on live GGD 04. A8 set up, not run. |
| Reply-matching logic | Two-key lookup, 19 offline tests, verified byte-identical to the deployed node by SHA-256. |
| Suppression (A9) | Fixed structurally as a routing branch. Both legs exercised on the live workflow. |
| Manual-review queue | Built. Unmatched replies raise a To-Do activity on the review inbox record (`crm.lead` id 8). |
| Odoo addon `ggd_crm` | 19.0.1.2.0 upgraded ✅. 19 control tests pass. Fields added: ggd_last_message_date, ggd_finalize_send(). |
| Workflow 3, outbound | **Built and tested.** Schedule trigger and candidate query added to the existing workflow, feeding the verified gate chain. Sends correctly, blocks correctly, duplicate-send protection proven. Inactive. |
| Error handling | **Settled 19 Aug. The handler works.** 88 deliberate failures, 88 catches. Manual runs bypass it; scheduled runs do not. See C0. |
| A8 Odoo unavailable | **PASS**, 18 Aug. Clean failure, no partial write, record unchanged. |
| C2 sanitised error notes | **PASS**, 18 Aug. Handler record carried workflow, execution ID and opportunity context; a pattern scan of the full 14,666-character payload found no credentials of any class. |
| Section B outbound | **B1–B4 PASS**, 19 Aug, against the owner mailbox. B5 outstanding — needs a deliberate SMTP credential failure. |
| Work selection / triggers | **Workflow 3 done. Workflow 5 unblocked** as of the 20 Aug upgrade — `ggd_last_message_date` is now on the model. |
| Odoo addon deployment | **19.0.1.3.0 deployed and verified 20 Aug.** `ggd_last_message_date` queryable, `ggd_finalize_send()` callable, and approval by direct write now stamps approver, approval time and basis-verified time — confirmed behaviourally, not just by the test run. |
| Backup and restore | Local backup exists. Off-computer copy still not done. Restore drill not run. |
| Lawful contact | Procedure drafted. **Not reviewed by a lawyer.** |

## Remaining before routine local use

1. **Run the addon upgrade to 19.0.1.3.0.** Two things depend on it: the
   approval-timestamp fix (approval by any route stamps approver and time, so
   more than one fixture can pass the gate), and `ggd_last_message_date`, which
   Workflow 5's query needs and which is not on the running model.
2. **Run B5** — the only outstanding Section B test. Duplicate the SMTP
   credential, give the copy a wrong password, point Workflow 3 at it for one
   run, then switch back. An invalid *recipient* does not work: the server
   accepts it and the send succeeds.
3. **Decide on bounce handling.** "Message sent" is currently an assumption.
4. Build Workflow 5's work-selection layer, after step 1.
5. Copy a backup to encrypted storage off this computer.
6. Run the isolated restore drill, including confirming the n8n encryption key
   makes restored credentials readable.
7. Get the lawful-contact procedure reviewed by a qualified German lawyer, and
   write the Art. 14 information text and Art. 6(1)(f) balancing note.
8. Prune the surplus workflow copies: `04b`, `04d`, `04s`, `04t`, `03s`, `98t`.
9. Activate workflows one at a time, only after their checklist passes, keeping
   outbound sending manually gated.

## Time estimate

Revised upward from 16 August, mainly because item 4 was not previously
accounted for and because the defect-discovery rate has been high.

| Work | Estimated focused time |
| --- | ---: |
| Addon upgrade, C0 proof, A8 | 1–2 hours |
| Section B outbound acceptance | 3–5 hours |
| Section C error handling, once C0 is settled | 3–4 hours |
| Work-selection layer and its tests | 8–15 hours |
| Off-computer backup and isolated restore drill | 3–4 hours |
| Final local acceptance review | 1–2 hours |
| **Local system ready for controlled use** | **19–32 hours** |

Add contingency for further defects. Every testing session so far has found at
least one, and the remaining areas are less exercised than Workflow 4 was.

Legal review is calendar time rather than your hours, and is not included.

## Completed Today (18 August 2026)

### Session Work (3.5 hours)

✅ **Addon upgrade** — 19 tests passing, send finalization methods added  
✅ **Design complete** — WORK-SELECTION-DESIGN.md (architecture & SQL queries)  
✅ **Implementation spec** — WORK-SELECTION-IMPLEMENTATION.md (node-by-node guide for n8n)  
✅ **Test suite** — WORK-SELECTION-TESTS.md (12 acceptance tests WS-B1–WS-D2)  
✅ **Test checklist** — Execution guide with checkbox tracking  
✅ **Test fixtures** — Automated setup script (WS-F1–F5 created)  
✅ **Test inputs** — 8 pre-made JSON payloads for manual testing  
✅ **C0 proof** — 2-minute error-handler validation guide  
✅ **Unit tests** — 5 new tests for send finalization (all passing)

**See:** [SESSION-SUMMARY-20260818.md](SESSION-SUMMARY-20260818.md) for detailed breakdown.

## Next single action

**Build Workflow 3 (Approved Send) in n8n:**

1. Open [WORK-SELECTION-IMPLEMENTATION.md](WORK-SELECTION-IMPLEMENTATION.md) sections 3.1–3.12
2. Build nodes one at a time (3.1 Schedule → 3.11 Finalize Send)
3. Test manually using payloads from [workflows/test-inputs-workflow3.json](workflows/test-inputs-workflow3.json)
4. Run WS-B1–B5 tests from [WORK-SELECTION-TEST-CHECKLIST.md](WORK-SELECTION-TEST-CHECKLIST.md)

**Each test:**
- Copy test payload from test-inputs-workflow3.json
- Paste into manual trigger
- Verify output matches "expected result"
- Tick off on checklist

**Estimated time:** 3-5 hours for Workflow 3 (complete) + 2-3 hours for Workflow 5.

**Everything you need is documented. No guessing required.** Follow the guides in order.
