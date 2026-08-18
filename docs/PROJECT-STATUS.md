# Project Status — 18 August 2026

Supersedes the 16 August status. Detailed test evidence lives in
[QA-TEST-PACK.md](QA-TEST-PACK.md); the history of how the reply-matching design
was reached is in [QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md) and
[WORKFLOW4-MATCHING-DESIGN.md](WORKFLOW4-MATCHING-DESIGN.md).

## Plain-language summary

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

## Where each area stands

| Area | Status |
| --- | --- |
| Workflow 4, reply analysis | A1–A7 and A9 pass on live GGD 04. A8 set up, not run. |
| Reply-matching logic | Two-key lookup, 19 offline tests, verified byte-identical to the deployed node by SHA-256. |
| Suppression (A9) | Fixed structurally as a routing branch. Both legs exercised on the live workflow. |
| Manual-review queue | Built. Unmatched replies raise a To-Do activity on the review inbox record (`crm.lead` id 8). |
| Odoo addon `ggd_crm` | 19.0.1.2.0 upgraded ✅. 19 control tests pass. Fields added: ggd_last_message_date, ggd_finalize_send(). |
| Workflow 3, outbound | Design complete. 15-minute schedule trigger + candidate query specified in WORK-SELECTION-IMPLEMENTATION.md. Ready for n8n builder. |
| Error handling | **Unproven — see C0 in the test pack.** Wiring is correct; the handler has never fired. |
| Work selection / triggers | **Design complete** ✅. WORK-SELECTION-DESIGN.md, WORK-SELECTION-TESTS.md (8 tests), and WORK-SELECTION-IMPLEMENTATION.md ready. Awaiting n8n implementation (8-15 hours). |
| Backup and restore | Local backup exists. Off-computer copy still not done. Restore drill not run. |
| Lawful contact | Procedure drafted. **Not reviewed by a lawyer.** |

## Remaining before routine local use

1. Run the addon upgrade. It gates the send-key work and all of Section B.
2. Settle C0 — prove whether the error handler fires, using `GGD 98t`. If it
   does not, that blocks sign-off on its own.
3. Run A8, then Section B (B1–B5) against your own mailbox only.
4. Build the work-selection layer: a trigger and a filtered query per workflow,
   each with Always Output Data and its own tests.
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
