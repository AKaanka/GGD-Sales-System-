# GGD Sales System — Current Acceptance Tests

Status: **in progress**. This pack addresses hardening items 2–6 in
[PROJECT-STATUS.md](PROJECT-STATUS.md); those items remain open until every
required result below is recorded as passing.

Historical findings and retracted hypotheses are kept separately in
[QA-INVESTIGATION-LOG.md](QA-INVESTIGATION-LOG.md). They are evidence, not
instructions.

## Safety rules

1. Run one test at a time. Stop on the first unexpected result.
2. Keep production-capable workflows inactive while testing manually.
3. Use fictional records and `.invalid` addresses only.
4. Never send to a prospect. Any email-send test requires Kaan's explicit
   approval immediately before that test and must use only Kaan's own mailbox.
5. Create a fresh backup before restore, failure-injection, or email tests.
6. Do not display or copy credential values into notes, screenshots, or Git.
7. Run `./scripts/validate-project.sh` after tracked configuration changes.

## Baseline already verified

| Control | Current evidence |
| --- | --- |
| Local services | Odoo and n8n health checks passed |
| Network exposure | Odoo and n8n bind to `127.0.0.1`; database ports are unpublished |
| Secrets | Local `.env` is ignored by Git |
| Odoo automation user | Restricted CRM access; no Settings administrator role |
| Error workflow | All five main workflows reference the shared error handler |
| Workflow activation | Main workflows inactive; shared error handler active |
| Outbound gate | Requires approval, no suppression, and a non-empty contact basis |

**GGD 04c was ported into live GGD 04 on 18 August 2026.** The live workflow now
carries the two-key matching, the suppression branch, the review queue, the
confidence threshold and the Always Output Data fix. Verified by comparing node
names, the full connection graph, the per-node alwaysOutputData / executeOnce /
retryOnFail flags, and the matcher source byte-for-byte: both sides produce the
identical signature `5589a868be9bde6d`. The workflow remains **inactive**, the
error-handler wiring is preserved, and IMAP remains disabled.

**A1 and A9 re-run and passed against live GGD 04 on 18 August 2026.**

- A1: reply from `f5@ggd-qa.invalid`, matched on sender alone to id 7,
  classified `information` at 0.95, and a real recommendation was written
  ("Prepare and send the price list and reference documents"). Approval and
  suppression flags unchanged.
- A9: reply from `f4@ggd-qa.invalid`, again an enthusiastic meeting request.
  Classified `meeting` at 0.95, and the suppression branch still overrode it —
  `ggd_suggested_next_action` reads "No action - contact is suppressed (do not
  contact)", `ggd_do_not_contact` stayed true, approval stayed false.

Together these exercise both legs of the suppression branch on the live
workflow, not just on the WIP copy. F1, F2 and F3 were verified unchanged by
both runs.

**A2, A3 and A4 also re-run and passed against live GGD 04 on 18 August 2026.**

- A2: reply from the shared address produced two review notes
  (`mail.message` 197 on id 5, 198 on id 4) and **no field writes on either
  record** — both still show no category, no confidence, no message ID, and
  their approval flags unchanged. The LLM branch never ran.
- A3: reply from `andere-person@ggd-qa.invalid`, an address matching nothing,
  carrying F5's message ID. Resolved through the thread search to id 7 and
  classified `referral` at 0.88.
- A4: reply from `voellig-unbekannt@ggd-qa.invalid` with no thread header
  matched neither key and raised review activity 7 on the inbox record, with
  the Message-ID correctly escaped and visible.

**All of A1–A7 and A9 now pass on the live workflow, not only on a WIP copy.**
A8 is the only Section A test outstanding, and it requires stopping the Odoo
container mid-run.

Rollback snapshots, all inactive: `GGD 04s` (live 04 before this port),
`GGD 04d` (04c before the matching rewrite), `GGD 03s` (03 before the send-key
wiring). `GGD 04b` is abandoned and `GGD 04t` is the injection harness. Prune
these once you are satisfied — five near-identical copies is how the wrong one
gets run.

## Fictional fixtures

| Fixture | Odoo ID | Purpose | Permanent state |
| --- | ---: | --- | --- |
| F1 | 3 | approved-send and approval-consumption history | Suppressed after test; do not clear |
| F2 | 4 | ordinary safe test record | Reusable |
| F3 | 5 | missing/invalid-data tests | Reusable |
| F4 | 6 | unsubscribe and suppression tests | Suppressed; do not clear |
| F5 | 7 | single-sender-match tests (A1) | Approved, not suppressed; reusable |
| Review inbox | 8 | holder for unmatched-reply review activities | Suppressed, no email; **do not delete** |

F2 and F3 deliberately share the address `shared@ggd-qa.invalid` — that is what
makes them the ambiguity fixture for A2. Do not "fix" one of them to a unique
address.

F5 was added on 18 August 2026 because A1 had no valid fixture: F1 and F4 are
the only records with unique addresses and both are permanently suppressed, so
any sender-only test against them necessarily exercises the suppressed branch
instead. F5 is `f5@ggd-qa.invalid`, basis `consent`, approved, not suppressed.

Do not reset F1 or F4 to an approved, contactable state. Create a new fictional
fixture whenever a test needs fresh approval.

## A. Reply workflow acceptance

### A1 — Single sender match

- Input: one fictional reply whose normalized sender matches exactly one
  fictional opportunity.
- Expected: the correct opportunity is selected; no other record is changed.
- Current status: **PASS on GGD 04c, 18 August 2026**, using the new F5 fixture.
  Reply from `f5@ggd-qa.invalid` with no `In-Reply-To`; matched on sender alone
  to id 7. Classified `information` at 0.92 with an accurate summary, and
  `ggd_suggested_next_action` received a real model recommendation ("Prepare and
  send price list together with relevant tooling reference cases"), confirming
  the non-suppressed leg writes normally. `ggd_do_not_contact` stayed false and
  `ggd_outreach_approved` stayed true. F2, F3, F1 and F4 were all verified
  unchanged by the run.

  Taken with A9, this exercises both legs of the suppression branch: the same
  workflow wrote a real next action for F5 and the fixed override for F4.
  Still to rerun on live `GGD 04` once 04c is ported.

### A2 — Ambiguous sender match

- Input: two opportunities with the same normalized sender.
- Expected: manual-review path; no CRM update and no LLM call.
- Current status: **PASS on GGD 04c, 18 August 2026.** Reply from
  `shared@ggd-qa.invalid` with no `In-Reply-To`. Both F2 (id 4) and F3 (id 5)
  were detected as candidates; the run took the manual-review branch and
  created one review note on each record (`mail.message` 179 on id 5, 180 on
  id 4), each naming both candidates. Verified afterwards that
  `ggd_reply_category`, `ggd_reply_summary`, `ggd_suggested_next_action`,
  `ggd_ai_confidence`, `ggd_do_not_contact` and `ggd_last_message_id` were
  unchanged on both records, and that the approval flags were untouched. The
  LLM branch never ran. Still to rerun on live `GGD 04` once 04c is ported.

### A3 — No sender match and valid thread fallback

- Input: no sender match, with a valid known outbound message/thread ID.
- Expected: one opportunity selected through the thread fallback.
- Current status: **PASS on GGD 04c, 18 August 2026.** The thread-fallback
  search was built for this test. A new `Get opportunities by thread` node runs
  on every execution alongside the sender search, filtering on
  `ggd_last_message_id`, so both keys are available to the decision node and the
  two-key logic lives in one place rather than being split across a branch.

  Tested with a reply from `kollege-unbekannt@ggd-qa.invalid` — an address
  matching no record — carrying F5's message ID in `In-Reply-To`. The sender
  search returned nothing, the thread search resolved F5, and the run matched
  with `matched_by: thread_fallback`. The model classified it `referral` at 0.90,
  which is the right reading of "I am taking over from my colleague". F1 to F4
  were all verified unchanged.

  Sender match still takes precedence over the thread search when both resolve;
  there is an offline test asserting that ordering.

### A4 — No sender or thread match

- Input: no sender match and no valid fallback.
- Expected: manual-review/error note only; no CRM reply fields updated.
- Current status: **routing correct on GGD 04c, 18 August 2026, after fixing a
  silent-drop defect. Not a full pass — the review terminus is still a dead
  end.**

  **Defect found and fixed.** The first A4 run ended at
  `Get many opportunities` in 339 ms. The search returned zero candidates, and
  n8n does not execute downstream nodes when a node returns no items — so
  `Evaluate reply match` never ran. An unmatched reply produced **no CRM record,
  no review note, and no error**. It disappeared. Every manual-review safeguard
  built into the decision logic was unreachable for the one case that most needs
  it, and nothing about the run looked like a failure: the execution was marked
  successful.

  Fixed by enabling **Always Output Data** on `Get many opportunities`, which
  emits one empty item so the decision node still runs. The empty item is
  filtered out downstream by the `id` check, so candidates remain zero and the
  review path is taken correctly. A node note records why the setting is
  required, because switching it off would silently restore the defect.

  **PASS on GGD 04c, 18 August 2026**, once the review queue was built. The
  dead end now routes to `Raise review activity`, which creates a **To-Do
  activity assigned to a human** on a dedicated holder record —
  `GGD Automation Review Inbox (do not contact, do not delete)`, `crm.lead`
  id 8, permanently suppressed and with no email address. Unmatched replies
  therefore appear in someone's activity list rather than only in a log.

  Verified: activity created on the inbox record, assigned to the
  Administrator, deadline today, note carrying sender, subject, Message-ID,
  In-Reply-To and the machine-readable reason. All five fixtures were
  unchanged by the run.

  **Second defect found and fixed during this test.** The first attempt wrote
  an empty Message-ID. Odoo sanitises activity notes as HTML, and
  `<fictional-reply-A4-002@example.invalid>` looks like an unknown HTML tag, so
  it was silently stripped — losing the single identifier a human needs to find
  the original email. The note now HTML-escapes every interpolated value.
  Anything written into an Odoo HTML field needs the same treatment.

  **Audit done, 18 August 2026 — the defect is contained.** Every Odoo node in
  Workflows 1, 2, 3, 5 and 99 uses `get` (single record by ID) or `create`, not
  a search that can return nothing, so none of them can drop work this way. The
  only affected nodes are the `Get many opportunities` nodes in the 04 family.
  04c is fixed; 04b and 04d still carry the defect but are an abandoned copy and
  a rollback snapshot, so neither should be run.

  **However, the audit surfaced something larger — see below.**

### Structural finding — the workflows do not select work

All five main workflows have the same shape:

```
manualTrigger -> set (hardcoded test input) -> odoo/get (one record by ID) -> ...
```

There is no schedule trigger and no query for candidate records anywhere. In
particular:

- **Workflow 3, "Approved Send and Record"**, does not poll for approved
  opportunities. It sends for one ID typed into a Set node.
- **Workflow 5, "Daily Follow-up Queue"**, does not build a queue. It processes
  one hardcoded ID.

This is entirely reasonable for manual safety testing, and matches the rule that
workflows stay inactive. But the selection logic is the part that decides *who
gets contacted*, and it does not exist yet. Section B currently tests the gate
on a record chosen by hand; it does not test that the right records are chosen
in the first place. Treat "Section B passes" as "the gate holds for a record I
picked", not "the system picks correctly".

Budget for this before activation: each workflow needs a trigger, a query with
an explicit filter, `Always Output Data` on that query, and its own tests.

### A5 — Malformed LLM JSON

- Inject malformed model output in a test-only copy.
- Expected: validation fails; no CRM reply fields updated; no response sent.
- Current status: **PASS, 18 August 2026**, on the injection harness
  `GGD 04t` (see note below). The model output was replaced with the truncated
  string `{"category":"interested","summary":"abc` instead of an object. The run
  routed to `Record invalid reply-analysis output`, wrote audit note 188 on
  lead 7, and left every field on F5 unchanged. Notably the code node did **not**
  crash on a non-object payload — it degraded to a validation failure, which is
  the desired behaviour given it has no try/catch.

### A6 — Low confidence

- Inject valid output below the configured confidence threshold.
- Expected: manual review; no unattended action.
- Current status: **control was missing and has now been built; test run is
  inconclusive.** Investigation on 18 August 2026 found that
  `Code in JavaScript` validated the reply category, a required summary, a
  required next action, and that confidence lies within 0–1 — but there was **no
  low-confidence threshold anywhere in the workflow**. Output at 0.30 confidence
  would have been written to the CRM exactly like output at 0.99. The test could
  not have passed because nothing implemented it.

  The threshold now lives on `If1`, which requires
  `ggd_reply_validation_ok && reply_analysis.confidence >= 0.7`, so low
  confidence follows the same manual-review path as invalid output. It is
  defined in one place only, as this section requires. **0.7 is a placeholder —
  choose the real value deliberately.**

  **PASS on GGD 04c, 18 August 2026.** Exercised by temporarily raising the
  threshold to 0.99 and replaying the F5 reply, which the model scored at 0.92.
  The run terminated at `Record invalid reply-analysis output` rather than the
  update, wrote audit note `mail.message` 186 on lead 7 with subject "GGD reply
  analysis failed validation", and left every field on F5 at its A1 value — same
  category, same confidence, same next action, same message ID. Low-confidence
  output was not applied. The threshold has been restored to 0.7.

  Note the run also proves the gate sits *after* matching: the log shows
  `matched_by: sender_only` and `opportunity_id: 7` resolved correctly before
  `If1` rejected on confidence. Matching and confidence are independent
  concerns, as they should be.

### A7 — Out-of-range confidence

- Inject confidence below 0 or above 1.
- Expected: validation fails and the invalid-output audit note is recorded.
- Current status: **PASS, 18 August 2026**, on the injection harness `GGD 04t`.
  Injected an otherwise valid analysis at confidence 1.5. The run routed to
  `Record invalid reply-analysis output`, wrote audit note 187 on lead 7, and
  left F5 unchanged.

  One caveat on what this proves. The range check in `Code in JavaScript` fires
  first, so the value never reaches Odoo and `_check_ggd_ai_confidence` is not
  exercised from the n8n side. That is correct defence-in-depth — the outer
  layer should catch it — but it means the Odoo constraint itself remains tested
  only from the Odoo side. If you want the original intent of this test, the
  code-node range check has to be bypassed deliberately.

### Injection harness — `GGD 04t`

`GGD 04t - injection tests A5/A7 (test harness, never activate)` is a copy of
04c with the model replaced by a Set node that emits a fixed payload, so bad
output can be produced on demand without depending on the model. It has no
credentials for Anthropic and costs nothing to run.

**It must never be activated and must never be ported over `GGD 04`.** Delete
it once A5 and A7 are signed off, or keep it deliberately as a regression
harness — but if kept, re-verify it still mirrors 04c after any change to the
real workflow, or it will quietly test something that no longer exists.

### A8 — Odoo temporarily unavailable

- Create a fresh backup and record the exact Compose project and service names.
- Stop only the Odoo application container; do not stop or delete its database.
- Execute the test workflow and then restart Odoo.
- Expected: sanitized error handling; no secrets; no duplicate CRM write after
  recovery.
- Current status: **not run — set up and ready.** Live GGD 04's test input is
  already loaded with a case that succeeds normally (reply from
  `f5@ggd-qa.invalid`, message ID `<live04-A8-001@example.invalid>`), so any
  failure is unambiguously caused by Odoo being down rather than by the input.

  To run it:

  1. Note F5's current state first — it should read category `referral`,
     confidence 0.88, message ID `<live04-A3-001@example.invalid>`. This is the
     baseline that must be unchanged after the failed run.
  2. `docker compose stop odoo` — **only the app container. Do not stop
     `odoo-db`.**
  3. Open GGD 04 and click Execute workflow. Expect a failure at
     `Get many opportunities`, the first node that reaches Odoo.
  4. `docker compose start odoo`, wait for it to answer on 8069.
  5. Check that GGD 99 recorded the failure, and that the record contains the
     workflow name, execution ID, failing node and a short error summary — and
     **no credentials, no API keys and no full email body** (this doubles as
     evidence for C2).
  6. Re-read F5. It must still show `referral` / 0.88 /
     `<live04-A3-001@example.invalid>`. Any change means a partial write got
     through.
  7. Click Execute again with Odoo back up. It should now succeed and write
     `<live04-A8-001@example.invalid>`, proving the item is re-runnable rather
     than poisoned.

  The failure is expected to land on a read, before any write, so the likely
  outcome is a clean failure. The point of the test is to prove that rather
  than assume it.

**Related finding, 18 August 2026 — model call timeouts.** During the A6 attempt
the `Basic LLM Chain` failed twice with "Request timed out", both times at
almost exactly 10.5 seconds, while earlier successful runs the same evening
completed in 6.2 and 6.6 seconds. That is a hard timeout being hit, not a random
network fault: normal variation in model latency is enough to break the run.

`Anthropic Chat Model` has no options configured and `retryOnFail` is false, so
a slow response fails the whole execution. The failure is at least safe — it
happens before any Odoo write, and F5 was verified unchanged afterwards — but an
unattended workflow would drop replies whenever the API is slow.

**Resolved the same evening.** `Basic LLM Chain` now has `retryOnFail` with
`maxTries` 3 and a 2 second wait, and `Anthropic Chat Model` carries an explicit
60 second timeout. The next run completed in 5.9 seconds and A6 passed. A retry
is safe here in a way it is **not** on the outbound send node — this call has no
external side effect, so a repeat cannot double-send. That distinction is
recorded in a node note on the chain so it does not get copied carelessly; B5
still requires the send node to have no retry at all.

### A9 — Reply to a suppressed lead

- Use F4 without clearing suppression.
- Expected: `ggd_do_not_contact` stays true, approval stays false, and the
  suggested action never recommends sending or following up.
- Current status: **PASS on GGD 04c, 18 August 2026.** Reply from
  `f4@ggd-qa.invalid` deliberately chosen to be the hardest case — an
  enthusiastic German meeting request ("Das klingt sehr interessant... einen
  Terminvorschlag fuer naechste Woche"). The model classified it correctly as
  `meeting` at 0.97 confidence with an accurate summary, and the suppression
  branch still overrode it: `ggd_suggested_next_action` reads "No action -
  contact is suppressed (do not contact)", `ggd_do_not_contact` stayed true,
  `ggd_outreach_approved` and `ggd_outreach_approved_by` stayed false, and the
  reply was recorded with its message ID. The run also incidentally proves the
  sender-only match path, since F4 was resolved from its address alone.
  Still to rerun on live `GGD 04` once 04c is ported.

  The remedy is a routing branch rather than a per-field guard: a
  new `If2 - contact suppressed` node sits between `If1` and the Odoo write and
  tests `ggd_do_not_contact || reply_analysis.category === 'unsubscribe'`.
  Suppressed replies go to `Update an opportunity (suppressed)`, which still
  writes category, summary, confidence and message ID, forces
  `ggd_do_not_contact` true, and writes a fixed
  "No action - contact is suppressed" next action instead of the model's
  suggestion. The analysis still runs, because a reply from a suppressed
  contact must still be recorded.

## B. Outbound workflow acceptance

**Static inspection of Workflow 3, 18 August 2026 (no send performed).** The
structure is sound and matches the shared rule:

```
Test input -> Get current opportunity before outbound gate
           -> Apply fresh outbound approval gate
           -> Outbound allowed?  --true--> Send an Email -> audit -> consume approval
                                 --false-> blocked-gate review note
```

The Odoo read sits immediately before the gate and the gate immediately before
the send, so the record is re-read in the same run rather than trusted from
earlier. The gate code checks all three conditions — `ggd_outreach_approved`,
`ggd_do_not_contact` and `ggd_contact_basis` — which is what B2, B3 and B4
require. `Send an Email` has `retryOnFail` false and no error override, which is
what B5 requires; do not change it.

### Behavioural test of the outbound gate, 18 August 2026

The gate code was executed directly against a matrix of records, without
modifying it, to see what it actually permits. Results:

| Record state | Gate verdict | Correct? |
| --- | --- | --- |
| All conditions met | allow | yes |
| `ggd_outreach_approved` false | block | yes |
| `ggd_do_not_contact` true | block | yes |
| `ggd_contact_basis` empty | block | yes |
| Suppressed **and** approved | block | yes — suppression wins |
| **No recipient address** | **allow** | **no** |
| **Basis `referral`** | **allow** | **no** |
| **Contact-basis note empty** | **allow** | **no** |

The first five are the controls B2, B3 and B4 depend on, and they hold.

**The gap that matters: the gate checks only that a contact basis is
non-empty, not which basis it is.** `referral`, `other` and
trade-fair-without-opt-in are never a lawful basis for a first marketing email
under [LAWFUL-CONTACT-PROCEDURE.md](LAWFUL-CONTACT-PROCEDURE.md) section 4. The
Odoo addon now refuses to approve those, but the send workflow was relying on
that entirely. Any record approved before the addon guard existed, or approved
through a path that bypasses it, would still have sent.

**Fixed additively** with a second check, `Lawful basis and recipient present?`,
between the main gate and the send-key check. It refuses the no-email bases,
refuses a send with no recipient address, and refuses a record with no approval
timestamp. It reads the record independently rather than trusting the earlier
gate's verdict.

### Work-selection layer and gate results, 18 August 2026

The schedule trigger and candidate query were added to the existing GGD 03
rather than to a new workflow, so the verified gate chain is reused rather than
duplicated. The workflow remains **inactive**; the trigger does nothing until it
is activated deliberately.

| Test | Record | Result |
| --- | --- | --- |
| WS-B1 candidate query | — | **PASS.** Selects exactly ids 4 and 7: approved, not suppressed, active. |
| WS-B4 suppression guard | F4, id 6 | **PASS.** Blocked at the main gate, review note written, `Send an Email` never ran. |
| Message-ID guard | F5, id 7 | **PASS.** Blocked at the main gate because an outbound Message-ID is already stored. |
| Approval-evidence guard | F6, id 144 | **PASS.** Passed the main gate, then blocked by `Lawful basis and recipient present?` because `ggd_outreach_approved_at` was empty. |

**Defect found by the first scheduled run, and fixed.** Adding the schedule
branch broke every scheduled execution with
`Node 'Test input - Fictional Opportunity' hasn't been executed`. Two downstream
nodes — `Prepare blocked-gate review note` and `Prepare send audit record.` —
read the opportunity ID from the manual test-input node, which does not run on
the scheduled path. Both now read the ID from the record that was actually
fetched and gated, which is correct on both paths and is the more truthful
source anyway.

This is the same failure mode as the Workflow 4 rewiring earlier: adding a new
entry point silently invalidates references that assumed the old one. **After
any rewiring, search the whole workflow for references to nodes that no longer
run on every path.** A programmatic check now confirms none remain.

**Why F6 had to be created.** F5 could not exercise the approval-evidence check,
because the main gate blocks it earlier for a different reason — it already has
an outbound Message-ID. A test that is blocked for the wrong reason proves
nothing about the control you meant to test. F6 was created specifically to pass
the main gate and fail only on the missing timestamp.

**The underlying defect this exposed.** F5 and F6 were both approved by a direct
`create`, which passed the approval guard but never stamped
`ggd_outreach_approved_at` — only the approval button did that. Since the send
key is derived from the approval time, such a record's key never changes, so
revoking and legitimately re-approving it would leave it permanently unsendable.
Fixed in ggd_crm **19.0.1.3.0**, which stamps approver, approval time and
basis-verified time on every approval route, with two new tests. **That upgrade
has not been run yet**, so records approved by direct write still lack the
timestamp until it is.

### Send-key duplicate protection built, 18 August 2026 — not yet run.
Inspection found no send-key logic at all, so nothing prevented a repeat run
from sending twice.

The key could not be "opportunity ID + draft version" as originally specified,
because there is no draft version: Workflow 2 stores drafts as `mail.message`
notes, and no draft note exists in the database at all. The key used instead is
**opportunity ID + `ggd_outreach_approved_at`** — one approval authorises one
send, which is exactly the compliance model this system runs on, and it does not
depend on drafts existing.

Workflow 3 now reads:

```
Outbound allowed?  --true--> Send key unused?  --true--> Claim send key before SMTP -> Send an Email -> ...
                                              --false-> blocked-gate review note
```

The key is claimed **before** SMTP. A crash between claiming and sending leaves
the key claimed, so the failure mode is a missed send that a human can
investigate — never a duplicate. This closes the specific window B1 cares about:
approval is consumed *after* the send, so a crash in between would previously
have left approval intact and allowed a second send on rerun.

Two things still outstanding. The gate does not verify a recipient address is
present. And this cannot run until the addon is upgraded — the fields
`ggd_last_send_key` and `ggd_last_sent_at` are new in ggd_crm 19.0.1.2.0 and do
not exist in the database yet, so the claim node will fail until then.

Snapshot before the change: `GGD 03s - snapshot before send-key wiring`.
Inspection is not a substitute for running B1–B5 with your own mailbox.

Use a newly created fictional fixture for B1–B5. Do not reuse F1 or F4.
Before any actual email test, Kaan must explicitly approve that single test and
the recipient must be Kaan's own mailbox.

### B1 and B2 — RESULTS, 19 August 2026

**B1 — controlled send: PASS**, on fixture F7 (`crm.lead` id 175), recipient the
owner mailbox, receipt confirmed.

| Check | Result |
| --- | --- |
| Email delivered | yes |
| `ggd_last_send_key` written | `175-2026-08-19 09:25:05` |
| `ggd_last_message_id` recorded | yes |
| Approval consumed | true to false |
| Unrelated fields untouched | `probability` still 50 |

**B2 — send-key idempotency: PASS**, on fixture F8 (`crm.lead` id 176).

Getting a *meaningful* result took four attempts, and the first three matter,
because each looked like a pass and proved nothing:

1. Re-running after the send blocked at the **approval gate** — approval was
   already consumed, so the run never reached the key.
2. Re-approving and re-running blocked at the **Message-ID guard** — the stored
   outbound ID stopped it first.
3. A second identical attempt blocked the same way.

No email was sent in any of them, which is the safe outcome — but the send key
was never exercised. **"No email arrived" is not evidence that the control you
meant to test is working.**

F8 was built to leave exactly one possible blocker: approved, not suppressed,
`consent` basis with a note, recipient present, approval timestamp present, **no
stored Message-ID**, and `ggd_last_send_key` pre-set to the value the run would
compute — simulating a crash after claiming but before approval was consumed.
The run blocked, no email arrived, and the review note gave **no other reason**,
so the block is attributable to `Send key unused?` alone. The record was not
written to at all.

### Defects B1 exposed before it passed

The first B1 attempt sent an email and revealed four faults, three of them
silent:

| Defect | Consequence |
| --- | --- |
| Claim node inherited seven unrelated fields set to 0 when cloned | A successful send would have zeroed `probability`, `expected_revenue`, `ggd_fit_score` and `ggd_ai_confidence`, as a side effect of an idempotency check |
| Claim node's record ID expression was blank | The Odoo update targeted no record, **reported success**, wrote no send key — and the email went out anyway |
| `ggd_last_sent_at` written as an ISO timestamp | Rejected by Odoo's `%Y-%m-%d %H:%M:%S` format; this error is the only reason the previous defect never reached production data |
| `GGD controlled send audit` referenced `Prepare send audit record` without its trailing period | Latent since creation; unreachable until a send actually succeeded |

The blank-ID case is the one to carry forward: **an Odoo update with an empty ID
returns success and writes nothing**, so a safety control can report success
while doing nothing. See OPERATIONS.md.

### B1 — Duplicate-send prevention

- Execute the same approved item twice.
- Expected: one email at most; the second execution is blocked and audited.
- Status: not run formally.

### B2 — Approval consumed after send

- Expected after one successful controlled send: approval becomes false and
  the send/message audit reference is stored.
- Status: observed previously; rerun formally with a fresh fixture.

### B3 — Suppression gate

- Set `ggd_do_not_contact = true`.
- Expected: send node is not reached.
- Status: gate behavior observed; formal recorded run pending.

### B4 — Missing contact basis

- Remove the contact basis from an otherwise approved fictional record.
- Expected: send node is not reached and the reason is recorded.
- Status: not run formally.

### B5 — SMTP failure

- Use a controlled local or dedicated SMTP test service that cannot deliver to
  real recipients. Do not deliberately damage the normal Zoho credential.
- Expected: sanitized error handler, no approval consumption, and no duplicate
  send during retry.
- Status: test method not yet implemented.

## C. Error handling and least privilege

### C0 — SETTLED, 18 August 2026: the handler fires on production runs only

**Result: the error handler works.** `GGD 98t` was activated and ran 88 times
between 11:46 and 13:32 UTC, throwing deliberately each minute. GGD 99 caught
every one — failure execution 333 at 13:32:41.049, handler execution 334 at
13:32:41.103, 54 ms later. All handler runs completed with status `success`.
`GGD 98t` has been deactivated and confirmed stopped.

This proves the inference below was correct: **manual executions bypass the
error workflow; scheduled and other production executions do not.** The handler
is not broken. The gap was in how it was being tested.

Consequences:

- **C1** is satisfiable, but only against an activated workflow. A manual run
  will never fire the handler no matter how deliberately it fails.
- **B5** likewise. An uncertain send during a *manual* run leaves no handler
  record. If B5 is run manually it will appear to fail its own criterion for a
  reason that has nothing to do with the send logic.
- **A8** will produce a handler entry only if the run is triggered on a
  schedule, not by hand.

**C2 is still not satisfied.** All 88 failures produced **zero** Odoo records,
because `GGD 98t` carries no `opportunity_id`, so GGD 99 correctly took its
`Keep sanitized error in execution log` branch. To get an Odoo error note to
inspect for leaked credentials, the failing run must carry an opportunity ID —
for example by stopping Odoo mid-run on a scheduled execution of a workflow
that is processing a record. That is A8 and C2 in one test.

The original finding, kept for the record:

### C0 (original) — the error workflow had never fired

**Finding, 18 August 2026. This undercuts C1, C2, B5 and A8, so read it first.**

The wiring is correct: GGD 04, 04c, 04t and 03 all reference
`xMbI9hyKnfim5M1q` as their error workflow, and GGD 99 is active. But GGD 99's
most recent execution is **#84, from 16 August**, while 18 August produced
several genuine failures — two Anthropic timeouts and one node error on 04c.
None of them produced an error-handler execution.

The evidence points to n8n not invoking the error workflow for **manual**
executions. Every workflow here is inactive and manual-only, by design. So the
entire error-handling layer has never engaged for a real failure, and cannot
under the conditions this pack currently uses.

The "GGD reply analysis failed validation" notes in Odoo are **not** evidence to
the contrary. Those are written by the workflow's own
`Record invalid reply-analysis output` node on its normal path. They are not
error-handler output.

What this means below:

- **C1** cannot be satisfied by "cause one safe test-only failure" while
  everything is manual. Causing the failure is easy; the handler will not fire.
- **C2** has nothing to review — no error records exist to inspect for leaked
  credentials, because none have been produced.
- **B5** assumes the handler records "send outcome uncertain". On a manual run
  it will not, so an uncertain send would leave no trace at all. That is the
  most serious consequence, because it is the case where you most need a record.
- **A8** will fail cleanly but is unlikely to produce a handler entry.

Resolve before sign-off. **A ready-made proof workflow now exists:**
`GGD 98t - error handler proof (test only, delete after)`, id
`FvXkjOO4v2PyNpqI`. It contains exactly two nodes — a one-minute schedule
trigger and a code node that throws — and its error workflow is set to GGD 99.
It has no credentials, sends nothing, and writes nothing. It is currently
**inactive**.

To settle the question, roughly two minutes:

1. Note GGD 99's latest execution ID.
2. Activate `GGD 98t`.
3. Wait about 90 seconds so the schedule fires at least once.
4. **Deactivate it immediately.**
5. Check GGD 99's executions. A new one means the handler does fire for
   production executions and the problem is only that manual runs bypass it —
   so C1, C2 and B5 must be run against an activated copy. No new execution
   means the handler is broken outright, which is a much bigger problem and
   blocks sign-off entirely.
6. Either way, open the resulting GGD 99 record and check it for leaked
   credentials. That is C2's evidence, and it does not exist until this runs.
7. Delete `GGD 98t`.

Do not skip step 4. It is the only workflow in this project that has ever been
activated, and it should not stay that way.

### C1 — Shared error workflow

- For each main workflow, cause one safe test-only failure.
- Expected: the shared handler records a sanitized note and never includes
  credential values.
- Status: handler assignment passed; deliberate failure test pending per
  workflow.

### C2 — Sanitized audit notes

- Review all generated error notes.
- Expected: node/workflow context is useful, but passwords, API keys, SMTP
  credentials, tokens, and full sensitive payloads are absent.
- Status: partial; complete after C1.

### C3 — Odoo automation-user denial

- Attempt one read/write outside the required CRM scope using the automation
  credential.
- Expected: access denied while required CRM workflow actions still succeed.
- Status: group membership inspected; interactive denial test pending.

## D. Backup and restore acceptance

1. Create a new backup and copy it to encrypted storage outside this computer.
2. Prepare an isolated Compose project with explicitly different project,
   container, network, and volume names.
3. Restore the matching Odoo database/filestore pair and the matching n8n
   database/data pair.
4. Confirm Odoo assets load, the fictional CRM records exist, n8n opens, and
   workflows/credentials are present without sending email.
5. Record the restore duration and result.
6. Delete the isolated test environment only after Kaan reviews the exact
   container and volume names and explicitly confirms deletion.

Status: backup creation passed; isolated restore drill pending.

## Sign-off

Production outreach remains blocked until:

- every required test above passes;
- the suppressed-reply defect in A9 is fixed;
- the final Workflow 4 reply-matching design passes A1–A4;
- the lawful-contact procedure receives qualified legal review;
- a final backup and isolated restore drill pass; and
- Kaan explicitly approves production activation.
