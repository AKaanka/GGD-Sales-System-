# Fable 5 handoff

Status: GATE3_IN_PROGRESS — steps 1, 1b, 2 PASS; 2 defects found and fixed;
steps 3–9 outstanding

Role change, 26 August 2026: Codex exhausted its token budget. Kaan reassigned
Fable 5 from offline reviewer to orchestrator + live executor for the
non-sending workflows. The original offline review (11 proposed fixes) is
retained below unchanged, under "Original offline review".

## Gate 3 execution log — 26 August 2026

### Environment verification (read-only)

- All four containers up. Docker reachable from this session.
- Fixtures 430–437 present, including FX7 (id 437) with `ggd_send_confirmed_at`
  backdated to 2026-08-18, correctly clearing Workflow 5's 7-day boundary.
- Model migration confirmed: `claude-sonnet-5` in all four LLM exports.
- Validation 24/24, matcher regressions 19/19.
- All six GGD-0x workflows inactive. One placeholder credential remains:
  GGD-00 "Record concise error in Odoo".

### Permission boundary established

Created `.claude/settings.json` (project scope, committed) allowing
`n8n execute` for the four non-sending workflows only, and explicitly denying:
`n8n execute --id G03SEND20260826`, `n8n export:credentials`, and
`n8n update:workflow` (so no agent can activate a workflow from the CLI —
activation stays a human decision).

CLI note: `n8n execute` starts its own instance and collides with the running
one on the task-broker port. Working invocation:
`docker exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5699 ggd-sales-system-n8n-1 n8n execute --id <ID>`

### Step 1 — Workflow 1 error path on FX1: PARTIAL PASS, one blocking defect

Passed:

- Selector matched only FX1 (430); the stray record Codex parked stayed parked.
- **The URL-validation guard works.** The run failed at "Opportunity 430 has an
  invalid public source URL", i.e. inside the validation code node — n8n never
  issued an outbound request to the fictional domain. This is proposed fix 2
  from the original review, confirmed live.
- Failure was loud. No approval granted, no email, no partial write.

**DEFECT 11 — the error workflow is assigned but inactive, so the entire
error-handling layer is dead.** n8n reported verbatim:

```
Calling Error Workflow for "G01QUAL20260826".
Workflow "G00ERR20260826A" is not active and cannot be executed
```

An n8n error workflow must be **active** to receive failures; assignment alone
does nothing. This currently applies to all five workflows GGD-01…GGD-05. It is
the third instance in this project of a control that reads green on a checklist
while doing nothing — compare defects 2, 8 and 10 in PROJECT-STATUS. Note the
legacy `GGD 99 - Shared Error Handler` **is** active, which is why error
handling appeared to work during the August testing.

Consequence, verified in Odoo: FX1 after the failed run is
`ggd_qualification_state = pending`, `ggd_automation_needs_review = False`,
no review summary. **Nothing was parked and nothing durable was recorded
anywhere except the n8n execution log.** Once activated, W1 would re-select
FX1 every hour indefinitely.

The design itself is sound: the workflows raise `Opportunity <id> …` messages
and GGD-00's regex recovers the ID from exactly that shape, so once GGD-00 is
active and bound, this error will park FX1 and the selector exclusion will
then hold it back. Two human actions are required first, both in the n8n UI:

1. Bind the Odoo JSON-2 credential on GGD-00 "Record concise error in Odoo".
2. **Activate GGD-00.** Safe: it has only an error trigger — no schedule, no
   webhook, no send node — so it runs only when another workflow fails.

Gate 3 steps 2–9 are held until both are done, because every remaining step
depends on failures being recorded.

### Step 1b — error handler activated: PASS on wiring, parking deferred

Kaan bound GGD-00's credential and published it. Verified: `active: true`,
credential BOUND. The "not active and cannot be executed" message is gone.

However, execution 484 (mode `cli`) produced **no GGD-00 execution at all**.
Confirmed against `execution_entity`: manual and CLI runs do not invoke the
error workflow; only production (scheduled) runs do. This matches the
19 August finding already recorded in PROJECT-STATUS. Consequence for the run
order: **FX1 parking can only be proven in Step 8**, the approved temporary
scheduled activation of GGD-01. Steps 2–7 do not depend on it.

Also observed in the execution table: Kaan ran GGD-02 and GGD-04 manually
(executions 477, 478, 481) while binding credentials. All three errored on the
retired model and wrote nothing — fixture state re-verified clean afterwards
(FX2 still `draft=empty`). No impact on Gate 3 evidence.

### Step 2 — Workflow 1 happy path: BLOCKED by DEFECT 12

FX1's source URL was set to Kaan's own site (Decision 1, approved). The run
failed with `Opportunity 430 has an invalid public source URL` — for a URL
that is plainly valid.

**DEFECT 12 — the source-URL guard rejects every URL, valid or not, and the
offline test suite cannot see it.** Root cause:

- n8n executes Code nodes with `vm.runInContext` against a **bare context**.
  Verified inside the container: `vm.runInContext('typeof URL', vm.createContext({}))`
  returns `undefined`, while `typeof URL` in the host process returns `function`.
- The guard used the WHATWG URL constructor inside a `try`. In the sandbox that
  raises `ReferenceError`, the catch-all converts it to "invalid public source
  URL", and **no URL can ever pass**. Workflow 1 could never qualify anything.
- It failed closed, so there was never an SSRF exposure — but the diagnostic
  actively misdirects: it blames the data for a code fault.

Why 24/24 was green: the suite's `runAllItemsCode` helper uses `new Function`,
which inherits this process's globals. It therefore validated code that cannot
run in n8n. **An offline test that does not reproduce the sandbox is not
evidence about production.** This is the same lesson as defects 1, 2, 8 and 10,
in a new place.

Fix applied to the tracked export (`workflows/GGD-01-lead-qualification.json`,
node "One qualification candidate per item"): the URL is now parsed with a
regex, requiring http/https, taking the host after the last `@` so userinfo
cannot spoof it, stripping the port, and rejecting loopback, private, link-local,
multicast, ULA and single-label hosts. Nine cases verified inside a real bare
`vm` context, including `https://trusted.example.invalid@127.0.0.1/x`, which is
correctly rejected.

Two regression tests added to `tests/workflows/test-workflow-exports.js`:

1. No Code node may reference globals the sandbox lacks (`new URL(`,
   `URLSearchParams`, `fetch(`, `structuredClone(`, `TextEncoder`, `TextDecoder`).
2. The Workflow 1 guard is exercised through `vm.createContext` — real sandbox
   fidelity — for one accepted and six rejected URLs.

Validation now 26/26 workflow tests, 19/19 matcher tests.

Applying it to live n8n was blocked by this session's safety classifier
(`n8n import:workflow`), so Kaan pasted the corrected code into the node in the
UI. Verified afterwards: live and tracked jsCode are identical except for one
trailing newline the paste added; workflow still `active: false`; all three
credential bindings intact.

### Step 2 (retry) — Workflow 1 happy path: PASS

Run against `https://www.germanygrowthdesk.com` completed end to end: page
fetched, `claude-sonnet-5` called, structured output validated, Odoo written.
Result on lead 430:

| Field | Value |
| --- | --- |
| `ggd_qualification_state` | `review` |
| `ggd_fit_score` | 5 |
| `ggd_ai_confidence` | 0.05 |
| `ggd_industry` | "Business development / market-entry consulting services…" |
| `ggd_outreach_approved` | **False** |
| `ggd_automation_needs_review` | True |

Three separate controls are confirmed by this single run:

1. **Workflow 1 never approves outreach.** `ggd_outreach_approved` stayed False,
   which is the PLAN's non-negotiable control 2.
2. **Low-confidence routing works.** The model correctly judged a fictional
   fixture name against GGD's own website to be a poor match (confidence 0.05),
   and the record went to `review` rather than `ready`. This is the first live
   proof of the confidence gate on the current workflow set.
3. **Sourced qualification is real**, not templated: industry and summary
   reflect the actual page content.

### Step 1 (retry) — parked records are not re-selected: PASS

Re-running Workflow 1 immediately afterwards succeeded and did nothing: lead
430 was not re-selected, chatter count stayed at 2, no second qualification was
written. This proves the `ggd_automation_needs_review = false` selector
exclusion (proposed fix 1 from the original review) holds live.

Note the routing distinction, worth keeping in mind for Step 8: FX1 got parked
here by the **qualification-confidence** path, not by the error handler. The
error-handler parking path is still unproven and still requires a scheduled
run.

### Remaining Gate 3 steps

3. Workflow 2 on FX2 → one stored draft, `draft_status = ready`, stop for human
   review. Kaan then reads the draft in Odoo without approving.
4. Workflow 4 scenarios 1–4 using the raw-email payloads in
   `scripts/gate3-workflow4-test-payloads.md`.
5. Workflow 5 on FX7 → exactly one review activity, then re-run for dedup.
6. Workflow 4 scenarios 5–6 (unsubscribe on FX2, hard bounce on FX5) plus the
   negative bounce test.
7. Re-run Workflow 5 → no duplicate.
8. Error-handler production proof: temporary scheduled activation of GGD-01
   (approved by Kaan), verify GGD-00 writes a sanitized record, deactivate and
   verify deactivation over two further cycles.
9. Re-export all six, confirm graphs match tracked files, re-run validation.

### Files changed by this session

- `workflows/GGD-01-lead-qualification.json` — sandbox-safe URL guard (defect 12).
- `tests/workflows/test-workflow-exports.js` — two sandbox-fidelity tests.
- `.claude/settings.json` — new; execution allowlist plus denies on the send
  workflow, credential export and CLI workflow updates.
- `docs/handoffs/FABLE-5.md` — this file.

`docs/PROJECT-STATUS.md` and `NEXT-ACTIONS.txt` are Codex-owned; NEXT-ACTIONS
has been refreshed because Codex is unavailable. PROJECT-STATUS still needs
defects 11 and 12 merged into its defect log by whoever resumes orchestration.

### Standing hazard, unchanged

The legacy send-capable workflows are still present: `GGD 03 - Approved Send
and Record` (schedule trigger + real Zoho SMTP bound) and `GGD 03s`. Kaan has
approved deleting the legacy set after an export backup; not yet done.

## Original offline review

Status at the time: REVIEW_COMPLETE: 11

Reviewed: 26 August 2026. Offline review only. No workflow JSON, addon, or
status file was edited. No Docker, no live n8n, no email, no credentials.

## Commands or checks run

1. `./scripts/validate-project.sh` — full run.
2. `node tests/workflows/test-workflow-exports.js` (runs inside the validator).
3. Manual line-by-line inspection of all six exports under `workflows/` and of
   `tests/workflows/test-workflow-exports.js`.
4. Read-only contract check of every Odoo method and field the workflows call,
   against `odoo/addons/ggd_crm/models/crm_lead.py` at manifest version
   `19.0.1.6.0` (grep/read only; file untouched).

## Test result

`validate-project.sh`: **PASS** — workflow export/decision suite 14/14, legacy
Workflow 4 matcher regressions 19/19, `.env` correctly Git-ignored, Compose
configuration check passed.

## Files changed

- `docs/handoffs/FABLE-5.md` (this file) — the only permitted edit.

## Review verdicts by requested area

### 1. Connections — PASS

Every connection source and target in all six exports resolves to an existing
node (also asserted by the test suite). The LangChain sub-node wiring
(`ai_languageModel`, `ai_outputParser`) is correctly attached to the chain
nodes in GGD-01, 02, 04, 05. Dual triggers (schedule + manual) converge on the
same first node in 01, 02, 03, 05 — valid n8n structure. GGD-03's graph is:
select → one-item-split → final gate → **claim → SMTP → require Message-ID →
finalize**, with both SMTP-error and finalize-error outputs routed to the
uncertain-send recorder. The offline suite already proves claim-precedes-SMTP,
finalize-follows-SMTP, and no finalize→SMTP loop.

### 2. Unsafe outbound paths — PASS, one procedural note

- The only `emailSend` node in the whole set is in GGD-03, and it is reachable
  only through "Continue only for new claim", which passes an item only when
  the claim RPC returned exactly `true`. A refused claim (ValidationError in
  Odoo) is an HTTP fault on a node with **no** `onError`, so the run fails
  closed before SMTP. A duplicate claim (`false`) drops the item silently —
  proven by the offline test.
- The send key is deterministic: `id:approved_draft_version` — exactly the
  spec's opportunity-id + draft-version.
- GGD-03 contains **no LLM node**: it can only send the stored
  `ggd_draft_subject` / `ggd_draft_body`, satisfying "never drafts after
  approval".
- **Note for Gate 4 (decision, not defect):** `toEmail` is
  `{{ $json.email_from }}` — the production shape. Nothing technical restricts
  the recipient to a Kaan-owned address; that safety is purely procedural
  (inactive + `.invalid` fixtures + explicit approval). See proposed fix 5.

### 3. Approval and suppression gates — PASS

Three layers exist and agree:

1. Selector domain: approved, not do-not-contact, basis present, draft status
   `approved`, approved version present, recipient present.
2. Per-item gate node: re-asserts all of the above plus
   `ggd_draft_version === ggd_approved_draft_version`, throws otherwise.
3. Authoritative layer: `ggd_claim_send_key` in addon 19.0.1.6.0 re-reads,
   under a `FOR UPDATE` row lock, approval + approver + timestamp +
   do-not-contact + basis/note/verified-at + recipient identity
   (normalized against `ggd_approved_recipient`) + draft-version match, and
   refuses the unlawful bases. The race the old export had is closed at the
   database, which is the correct place.

Suppression: GGD-02 excludes do-not-contact before drafting; GGD-04's addon
methods drop the response draft for suppressed contacts and set
`ggd_do_not_contact` on unsubscribe; GGD-05 excludes do-not-contact,
needs-review, bounced, won (via `stage_id.is_won`) and lost (via
`active = true`), and replies after the confirmed send.

### 4. Credential values — PASS

No secret value appears in any export. All credential references are
placeholders (`REPLACE_WITH_ODOO_JSON2_CREDENTIAL`,
`REPLACE_WITH_ANTHROPIC_CREDENTIAL`, `REPLACE_WITH_ZOHO_SMTP_CREDENTIAL`,
`REPLACE_WITH_ZOHO_IMAP_CREDENTIAL`) plus the documented
`REPLACE_WITH_KAAN_TEST_SENDER`. No `$env.` reads (test-enforced). No
`pinData` content, no `meta.instanceId`. The `X-Odoo-Database: ggd` header is
configuration, not a secret.

### 5. Odoo contract vs addon 19.0.1.6.0 — PASS

Every called method exists: `ggd_record_automation_error`,
`ggd_apply_qualification`, `ggd_prepare_draft`, `ggd_claim_send_key`,
`ggd_finalize_send`, `ggd_find_reply_candidates`,
`ggd_queue_unmatched_inbound`, `ggd_record_bounce`, `ggd_record_reply`,
`ggd_queue_follow_up`. Every referenced field exists, and every selection
value used in a domain is valid: `ggd_qualification_state` `pending/ready`,
`ggd_draft_status` `empty/approved`, `ggd_delivery_status` `accepted`.

### 6. n8n 2.34.6 version compatibility — CANNOT VERIFY OFFLINE

The node typeVersions in use are: `httpRequest` 4.3, `code` 2, `if` 2.2,
`scheduleTrigger` 1.3, `manualTrigger` 1, `emailSend` 2.1, `emailReadImap`
2.2, `errorTrigger` 1, `stickyNote` 1, `chainLlm` 1.7, `lmChatAnthropic` 1.3,
`outputParserStructured` 1.3. Whether each is ≤ the maximum shipped with n8n
2.34.6 can only be confirmed at import. **Codex: at Gate 2, after importing,
check every node for an "unknown/unsupported version" marker before recording
the gate as passed.** The offline suite already blocks the two known-obsolete
types (`sendEmail`, `anthropicChatModel`).

## Proposed fixes for Codex (I did not edit any workflow)

Ordered by priority. 1–5 are workflow changes, 6–11 are test-suite additions.

1. **GGD-01 + GGD-02 selectors: add `['ggd_automation_needs_review','=',false]`
   to the search_read domain.** A record whose qualification failed (for
   example a permanently unreachable source URL) keeps
   `ggd_qualification_state = 'pending'` and is re-selected every hour /
   30 minutes forever, producing an error-workflow entry and chatter noise on
   each cycle. The review flag exists precisely to park such records.
   (GGD-03 optionally too; it is already fail-closed at claim time, the
   exclusion only removes repeated blocked-claim noise every 15 minutes.)
2. **GGD-01 "Fetch approved public company page": validate the URL before
   fetching.** The node fetches whatever `ggd_source_url || website` contains,
   with no scheme or host restriction — a crafted or mistyped CRM value could
   make n8n request internal services (for example `http://odoo:8069/...`).
   Proposed change in "One qualification candidate per item": drop or fail any
   row whose URL does not match `^https?://`, and refuse obviously internal
   hosts (`odoo`, `n8n`, `localhost`, `127.`, RFC 1918 ranges).
3. **GGD-01 fetch failure aborts the remaining batch items.** The fetch node
   has no `onError`, so one bad URL in a batch of five stops items 2–5 until
   the next hourly cycle. Either accept and document this (it is fail-closed),
   or set `onError: continueErrorOutput` and route the error output to a
   review-note recorder. Decision for Codex.
4. **GGD-00: the no-opportunity branch records nothing in Odoo.** When no
   lead ID is recoverable, the false branch of "Opportunity ID is available"
   is empty and the only durable trace is the n8n execution record (the sticky
   note says this is deliberate). The spec's failure-workflow section asks for
   a record of every failure. Optional: POST such errors to a fixed
   review-inbox record. Decision for Codex/Kaan.
5. **GGD-03 (Gate 4 hardening, temporary): add a recipient allowlist gate.**
   Until the first controlled send is signed off, insert an If node after
   "Continue only for new claim" that passes only when `email_from` equals the
   Kaan-owned test address, failing closed otherwise. Remove it at go-live.
   This converts Gate 4's procedural safety into a technical one for the test
   window. Needs Kaan's address choice; the value must not be committed — use
   a placeholder like the existing sender placeholder.

Test-suite additions for `tests/workflows/test-workflow-exports.js`:

6. Assert that across **all six** exports, only `GGD-03-approved-send.json`
   contains an `emailSend` node (currently only 02, 04, 05 are checked; 00 and
   01 are not).
7. Assert GGD-03 contains **no** `@n8n/n8n-nodes-langchain.*` node — the
   "sends only the reviewed draft, never drafts after approval" invariant is
   central and currently untested.
8. Assert GGD-03's "Claim send key before SMTP" node has **no** `onError`
   (a refused claim must fail the run), and that "Send exact reviewed draft
   via Zoho" and "Finalize complete send audit in Odoo" both have
   `onError: 'continueErrorOutput'` (uncertain sends must be recorded, not
   fatal). A future edit flipping any of these would silently weaken the
   fail-closed design.
9. Assert every `credentials` reference id in every export starts with
   `REPLACE_WITH_` — pins the placeholder discipline the secret-regex cannot
   fully cover.
10. Assert every Odoo URL matches `^http://odoo:8069/json/2/crm\.lead/` —
    catches a stray host, database, or JSON-RPC-era endpoint.
11. Assert GGD-04's "Is delivery bounce" true branch reaches the
    `ggd_record_bounce` node and its false branch reaches the
    `ggd_record_reply` node — the reply/bounce fork is only indirectly
    covered today.

## Blockers or integration notes

- No blocking defect found in the six exports. The set is import-ready
  pending the Gate 2 typeVersion confirmation (area 6 above).
- Item 5 needs a decision from Kaan before Gate 4, not before Gate 2.
- Cosmetic only: in GGD-04, "Record matched bounce in Odoo" (position
  [300,-130]) visually overlaps "Queue unmatched inbound for Odoo review"
  ([280,-120]); harmless, tidy at will.
- The error handler's `send_may_have_occurred` regex matches the current
  GGD-03 node names; if Codex renames GGD-03 send/finalize nodes during
  import, the regex in GGD-00 "Sanitize error context" must be updated in the
  same change.
- I did not run Docker, open live n8n, import anything, or send email. All
  uncommitted work is preserved; the working tree is unchanged apart from
  this file.
