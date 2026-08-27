# Claude Code handoff

Status: ODOO_GREEN: 108/108 at addon 19.0.1.8.0, live worker restarted 27 Aug 2026 09:23 UTC. Defect 13 closed; draft-clear defect closed.

(Gate 1 passed 26 August 2026 16:35 Europe/Berlin on Kaan's machine. The
BLOCKED: DOCKER_OFF entries below are retained as audit history — they
record that this Claude Code session's own shell never had Docker access;
the passing run was executed by Kaan in his macOS Terminal. See the Gate 1
result entry at the end of this file.)

## Commands run

```
docker --version
docker info --format '{{.ServerVersion}}'
docker compose ps
which -a docker
ls /usr/local/bin/docker /Applications/Docker.app/Contents/Resources/bin/docker "$HOME/.docker/bin/docker"
```

## Test result

Not run. `./scripts/run-addon-tests.sh` requires `docker compose exec -T odoo ...`
and could not be attempted.

## Read-only inspection performed

- Read AGENTS.md, PLAN.md, README.md, docs/ODOO-SETUP.md, docs/PROJECT-STATUS.md,
  docs/FOUR-AGENT-EXECUTION-PLAN.md as instructed.
- Confirmed `odoo/addons/ggd_crm/__manifest__.py` declares version `19.0.1.6.0`,
  depends on `crm`, installable, non-application.
- Addon layout: `models/crm_lead.py` (1653 lines), `tests/test_crm_lead.py`
  (1587 lines), `views/crm_lead_views.xml` (138 lines).
- `git status` (read-only, no changes made) shows a large uncommitted working
  tree, including uncommitted changes inside `odoo/addons/ggd_crm/**`
  (manifest, crm_lead.py +1094/-?, test_crm_lead.py +781/-?, views +70/-).
  This uncommitted work was left untouched, per instructions.
- `scripts/run-addon-tests.sh` exists and is executable; it shells out to
  `docker compose exec -T odoo ...` to run `odoo server --test-enable
  --test-tags /ggd_crm -u ggd_crm`.

## Files changed

None. No edits were made to any file in this task.

## Blockers or integration notes

`docker` is not available in the shell this Claude Code session runs
commands in (`docker: command not found`; no binary at any of the usual
install locations; PATH has no docker entry). This session's shell is a
sandboxed workspace on Kaan's machine with the project folder mounted, not
a direct macOS Terminal session — it cannot see Docker Desktop's CLI or
socket even if Docker Desktop is running on the host.

Practical implication: Gate 1 (Odoo addon upgrade + 102 tests) cannot be
executed from this Claude Code session as currently connected, regardless
of whether Kaan has started Docker Desktop. Someone with direct shell
access to Kaan's Mac (Kaan himself, in a normal Terminal, or a Claude Code
session attached that way) needs to run:

```
docker --version && docker compose version
```

and, once confirmed, `./scripts/run-addon-tests.sh`. If this Claude Code
instance is later reconnected with real Docker CLI access, it can pick up
Gate 1 immediately — the addon and test files are already substantially
built (see git diff stat above) and just need live verification.

No files were modified. No commit or branch change was made. No email was
sent and no n8n workflow was touched.

---

## Gate 3 fixture prep — 26 August 2026 (Odoo lane, orchestrator instruction)

Status: BLOCKED: DOCKER_OFF (unchanged — docker CLI still unavailable in this
session's shell; re-confirmed with `which docker` / `docker --version`
immediately before this entry).

### What was asked

Orchestrator instruction to prepare (not necessarily execute) an idempotent
fixture script for Gate 3 non-send functional testing: a pending-qualification
lead, a qualified-ready-to-draft lead, a do-not-contact lead, a stored+approved
draft lead reserved for Gate 4, and documented inbound-reply/bounce test data
for Workflow 4.

### What was created

- `scripts/create-gate3-fixtures.sh` — idempotent (matches existing records by
  exact fixture name before creating anything; safe to re-run). Uses the
  addon's own public API (`ggd_apply_qualification`, `ggd_prepare_draft`,
  `action_ggd_approve_outreach`) via `docker compose exec -T odoo odoo shell`,
  the same invocation pattern as `scripts/run-addon-tests.sh` and the existing
  `scripts/setup-work-selection-fixtures.sh`. Creates 7 fictional `.invalid`
  records:
  - **FX1** (`FX1_PENDING`) — pending qualification, has `ggd_source_url` set.
  - **FX2** (`FX2_QUALIFIED_READY`) — qualification applied via
    `ggd_apply_qualification`, `ggd_qualification_state = ready`, no draft yet.
  - **FX3** (`FX3_DO_NOT_CONTACT`) — `ggd_do_not_contact = True` from creation.
  - **FX4** (`FX4_APPROVED_DRAFT`) — qualified, drafted via `ggd_prepare_draft`,
    approved via `action_ggd_approve_outreach`. **Reserved for Gate 4** — its
    recipient is a `.invalid` address and MUST be replaced with a real
    Kaan-owned address (which revokes and requires re-approval) before any
    real Workflow 3 send test.
  - **FX5** (`FX5_SENT_SYNTHETIC`) — same qualify/draft/approve path as FX4,
    then a **synthetic** already-sent state is written directly
    (`ggd_send_confirmed_at`, `ggd_last_message_id`, etc.) purely so Workflow
    4's message-ID match and `ggd_record_bounce` paths have something to
    match against. No SMTP call was made, no email exists; this is the one
    fixture not produced through the real send path, and is documented as
    such in the script.
  - **FX6A / FX6B** (`FX6A_AMBIGUOUS` / `FX6B_AMBIGUOUS`) — two minimal leads
    sharing one email address, for the "ambiguous match" Workflow 4 test case.
  - Pipeline stage assignment is best-effort: the script looks up
    `crm.stage` by the names in `docs/ODOO-SETUP.md` and leaves `stage_id`
    unset (not an error) if a stage hasn't been created yet.
- `scripts/gate3-workflow4-test-payloads.md` — six documented JSON test
  payloads for manually triggering Workflow 4 against the fixtures above:
  matched-by-sender, matched-by-Message-ID, unmatched, ambiguous, unsubscribe
  (run after the matched-by-sender case, on the same lead, with a later
  timestamp), and hard bounce. Includes expected outcomes and two suggested
  negative/dedup tests. This file only documents test data — it does not
  import, edit, or execute any workflow.

### Verification performed without Docker

- `bash -n scripts/create-gate3-fixtures.sh` — outer shell script syntax OK.
- Extracted the embedded Python (the `odoo shell` heredoc) and ran
  `python3 -c "import ast; ast.parse(...)"` against it — syntax OK. This does
  **not** prove the script runs correctly against a live Odoo registry
  (`env`, `Lead`, `Stage` are only bound at `odoo shell` runtime) — that part
  is still unverified and requires live execution.
- Re-confirmed `docker` is not on PATH and not at any of the previously
  checked install locations; re-confirmed `host.docker.internal:8069` and
  `localhost:8069` are unreachable from this session's shell (the former is
  actively blocked by this session's network allowlist, the latter refuses
  the connection). No live Odoo access exists from here by any route
  currently available.

### Files changed

- `scripts/create-gate3-fixtures.sh` (new)
- `scripts/gate3-workflow4-test-payloads.md` (new)
- This file (`docs/handoffs/CLAUDE-CODE.md`), appended only.

No file inside `odoo/addons/ggd_crm/**` was touched. No commit was made, no
branch changed, nothing in `workflows/**` or `tests/workflows/**` was read
for editing purposes (only `crm_lead.py` and `N8N-AUTOMATION-SPEC.md` were
read, both read-only, to get field names and matching semantics right).

### Blocker (unchanged) and one new observation

Same Docker blocker as the earlier entry above — this session's shell still
has no `docker` binary and no reachable Odoo. The fixture script has **not**
been run, so there are no real record IDs yet; the CREATED/EXISTS summary
that `create-gate3-fixtures.sh` prints on a live run should be pasted into
this file once someone with real Docker access runs it.

Separately: `git status` in this pass surfaced
`warning: unable to unlink '.git/index.lock': Operation not permitted`, and a
0-byte `.git/index.lock` is currently present in the repository. `git status
--porcelain` still returned correct output despite the warning, and nothing
here ran any git write command, so no action was taken. This may just be a
leftover from an interrupted git operation, or it may mean another
participant (most likely Codex) is mid-operation on the shared repository
right now. Worth Codex checking before running its own git commands.

---

## Gate 3 fixture review fixes — 26 August 2026 (Odoo lane, orchestrator review)

Status: BLOCKED: DOCKER_OFF (unchanged — re-confirmed `docker` still not on
PATH in this session's shell immediately before and after these edits).

### Defects fixed, from the orchestrator's review

1. **Send-key shape (blocking).** FX5 previously used a hand-picked constant
   as `ggd_last_send_key`, which does not match the shape
   `_ggd_check_send_key_matches_approved_draft` (crm_lead.py:946) requires —
   `"<opportunity id>:<approved draft version>"` — so any write carrying it
   would have raised `ValidationError` (guard applies to plain writes too,
   crm_lead.py write(), not only to `ggd_claim_send_key`).
2. **Lingering approved+sent state.** Writing the synthetic sent-state
   fields and revoking approval in the same `write()` call would have hit
   write()'s suppression-wins guard, which silently drops
   `ggd_last_send_key` from any single write that also revokes approval —
   so the two must not be combined into one write.

**Fix applied — not the literal hand-write-twice fix, a stronger one:**
rather than hand-writing the sent-state fields and then a second manual
write to revoke approval, FX5 now calls the addon's own real send-side
methods directly: `ggd_claim_send_key(f"{fx5.id}:{fx5.ggd_approved_draft_version}")`
followed by `ggd_finalize_send(message_id=..., recipient=..., subject=...,
body_summary=...)`. This resolves both defects at the root rather than
matching their shape by hand:

- The send key is computed with the exact formula the guard itself uses
  (`_ggd_expected_send_key`), so it always matches by construction.
- `ggd_claim_send_key`'s write and `ggd_finalize_send`'s write are two
  separate `write()` calls (matching what the review asked for), and
  `ggd_finalize_send`'s own write never includes `ggd_last_send_key` in its
  values at all — so the suppression-wins key-drop branch never triggers for
  it, and it clears `ggd_outreach_approved`/`ggd_outreach_approved_by`/
  `ggd_outreach_approved_at`/`ggd_approved_recipient` explicitly and
  correctly in that second write. No record can end up lingering
  approved+sent.
- Neither method calls SMTP (that only happens in n8n's SMTP node, outside
  Odoo), so FX5 still never sends an email — the fixture's core guarantee is
  unchanged.
- The script now prints the real computed send key in its summary
  (`FX5 send key (id:approved_draft_version): ...`) instead of the old
  constant.

I flagged this deviation from the literal instruction explicitly here so it
can be checked: using `ggd_claim_send_key`/`ggd_finalize_send` directly is,
in my judgement, more robust than a hand-rolled second write, because it
exercises the addon's actual guarded code path (the same one Workflow 3
calls) instead of re-deriving its invariants by hand. Happy to switch to a
literal `action_ggd_revoke_outreach()` second call instead if the
orchestrator prefers that shape for readability — functionally the current
version already produces the requested two-write, non-lingering result.

3. **Raw email payload set added.** `scripts/gate3-workflow4-test-payloads.md`
   now has a second section, "Raw email payloads (Workflow 4 manual
   trigger / IMAP shape)", with one payload per existing scenario (matched
   by sender, matched by Message-ID, unmatched, ambiguous, unsubscribe, hard
   bounce) shaped as `{from, subject, messageId, inReplyTo, textPlain,
   date}` — the exact input shape
   `workflows/GGD-04-reply-and-bounce-intake.json`'s "Normalize and sanitize
   inbound email" node consumes. I read that node's code (read-only, not
   edited) to get the bounce-detection regexes and the DSN
   `Original-Message-ID:`/`X-Original-Message-ID:` extraction exactly right:
   the bounce payload uses a `mailer-daemon` sender and a body containing an
   `Original-Message-ID:` line pointing at FX5's outbound Message-ID, with
   no soft-bounce wording, so it resolves as `is_bounce: true,
   hard_bounce: true` and matches FX5 by exact Message-ID (the node requires
   an exact Message-ID match for a bounce, not just a sender match). The
   original six Odoo-method payloads are kept as the addon-level test set;
   this is additive, not a replacement.

### Verification performed without Docker

- `bash -n scripts/create-gate3-fixtures.sh` — outer shell syntax OK.
- Extracted the embedded Python and ran `python3 -c "import ast;
  ast.parse(...)"` — syntax OK (still cannot prove it runs correctly against
  a live Odoo registry; `env`/`Lead`/`Stage` only exist at `odoo shell`
  runtime).
- Extracted all 12 fenced ` ```json ` blocks from
  `gate3-workflow4-test-payloads.md` (6 original + 6 new) and ran
  `json.loads` on each — all parse.
- Re-confirmed `docker` is still not on PATH in this session's shell.

### Files changed

- `scripts/create-gate3-fixtures.sh` — FX5 section rewritten as described
  above; final summary print updated.
- `scripts/gate3-workflow4-test-payloads.md` — new "Raw email payloads"
  section appended.
- This file, appended only.

No file inside `odoo/addons/ggd_crm/**` was touched. No commit was made, no
branch changed. Docker was not run, per the orchestrator's instruction for
this pass.

### One process note

Earlier in this session a stale `.git/index.lock` was observed (reported in
the previous handoff entry above) with a warning that it could not be
unlinked. It is gone now — `.git/index.lock` no longer exists as of this
pass — so whatever produced it has resolved on its own. No action was taken
on it either time.

---

## Gate 3 fixture live run — 26 August 2026 (orchestrator)

The fixed script completed successfully against the local `ggd` database.
It created only fictional `.invalid` records; no n8n workflow ran and no email
was sent.

```text
CREATED  FX1_PENDING            id=430    [GGD-GATE3-FIXTURE] FX1 -- Pending Qualification (Nordlicht Fictional GmbH)
CREATED  FX2_QUALIFIED_READY    id=431    [GGD-GATE3-FIXTURE] FX2 -- Qualified, Ready to Draft (Baltic Gears Fictional AG)
CREATED  FX3_DO_NOT_CONTACT     id=432    [GGD-GATE3-FIXTURE] FX3 -- Do Not Contact (Rhein Fictional Handels UG)
CREATED  FX4_APPROVED_DRAFT     id=433    [GGD-GATE3-FIXTURE] FX4 -- Approved Draft, Reserved for Gate 4 (Schwarzwald Fictional Maschinenbau KG)
CREATED  FX5_SENT_SYNTHETIC     id=434    [GGD-GATE3-FIXTURE] FX5 -- Synthetic Already-Sent, For Reply/Bounce Match Tests (Alpen Fictional Logistik SE)
CREATED  FX6A_AMBIGUOUS         id=435    [GGD-GATE3-FIXTURE] FX6A -- Ambiguous Match Pair 1 (Fictional Duplicate Contact)
CREATED  FX6B_AMBIGUOUS         id=436    [GGD-GATE3-FIXTURE] FX6B -- Ambiguous Match Pair 2 (Fictional Duplicate Contact)
```

Gate 3 workflow execution remains unstarted and manual-trigger only.

---

## FX7 added — 26 August 2026 (Odoo lane, orchestrator instruction)

Status: BLOCKED: DOCKER_OFF (unchanged — re-confirmed `docker` still not on
PATH in this session's shell before and after this edit).

### What was asked

Add FX7, "Stale Confirmed Send, For Follow-Up Queue Test": built like FX5
(qualify, draft, approve, `ggd_claim_send_key`, `ggd_finalize_send` with its
own synthetic Message-ID `<gate3-fixture-fx7-001@ggd-gate3-fixture.invalid>`),
then backdate `ggd_send_confirmed_at`, `ggd_last_sent_at`, and
`ggd_last_message_date` by 8 days in a separate write so it clears
Workflow 5's 7-day staleness filter. No reply recorded. Idempotent. Confirm
(read-only) that write()'s guard does not block backdating those fields, or
report the blocker instead of working around it.

### write() guard check (read-only, no workaround needed)

Read `write()` in `odoo/addons/ggd_crm/models/crm_lead.py` before writing
the backdating code. Its special branches only trigger when the write's
`values` contain: a `GGD_APPROVAL_INPUT_FIELDS` member (`ggd_draft_subject`,
`ggd_draft_body`, `ggd_draft_version`, `email_from`), a `GGD_DRAFT_FIELDS`
member, `ggd_last_send_key`, `ggd_do_not_contact`, or `ggd_outreach_approved`.
`ggd_send_confirmed_at`, `ggd_last_sent_at`, and `ggd_last_message_date` are
none of those, and there is no `@api.constrains` on any of the three
(confirmed earlier by grepping every `@api.constrains` in the file — only
`ggd_fit_score` and `ggd_ai_confidence` have one). A write touching only
those three fields falls straight through to `super().write(values)`
unblocked. **No blocker found — nothing was worked around.**

I also cross-checked the actual Workflow 5 staleness threshold rather than
assuming: `workflows/GGD-05-daily-follow-up.json`'s candidate query domain
(`ggd_send_confirmed_at <= now - 7 days`, plus `active`, not-won,
`ggd_do_not_contact = false`, `ggd_automation_needs_review = false`,
`ggd_delivery_status = 'accepted'`) and `ggd_queue_follow_up()`'s own guard
in `crm_lead.py` (raises "not yet seven days old" when
`ggd_send_confirmed_at > now() - 7 days`) agree on the same field and the
same 7-day boundary. Backdating 8 days clears both with margin. That file
was read only, not edited.

### What was changed

`scripts/create-gate3-fixtures.sh`:

- New FX7 block, inserted after FX6A/FX6B and before the fixture summary.
  Reaches "confirmed sent" via `ggd_claim_send_key`/`ggd_finalize_send`
  exactly like FX5 (own qualification numbers, own draft text, own
  Message-ID `<gate3-fixture-fx7-001@ggd-gate3-fixture.invalid>`, own
  fictional company "Ostsee Fictional Feinmechanik OHG" — kept distinct
  from every other fixture's name/email so it can't collide with FX5's
  reply/bounce tests).
- A separate backdating write follows, gated on
  `fx7.ggd_send_confirmed_at > FX7_BACKDATE_TARGET` (target = `now() - 8
  days`, recomputed each run). Idempotent by construction: once
  `ggd_send_confirmed_at` has been backdated, it is only ever further in
  the past relative to a later run's freshly recomputed target, so the
  condition goes false and nothing is written on re-runs — no separate
  "already backdated" flag needed.
- `ggd_last_reply_received_at` is left untouched (never set for FX7), so
  `ggd_queue_follow_up()`'s reply check is naturally satisfied without any
  extra code.
- Final summary print block extended with FX7's Message-ID, computed send
  key, and post-backdate `ggd_send_confirmed_at` value.

`scripts/gate3-workflow4-test-payloads.md`: added a bullet to the existing
"## Notes" section explaining FX7 is for Workflow 5 (not Workflow 4, so it
has no scenario payload above it), and suggesting a dedup test — calling
`ggd_queue_follow_up()` against it twice should create one activity, then be
a no-op the second time.

### Verification performed without Docker

- `bash -n scripts/create-gate3-fixtures.sh` — outer shell syntax OK.
- Extracted the embedded Python (now 386 lines) and ran `python3 -c "import
  ast; ast.parse(...)"` — syntax OK. Still cannot prove live behaviour
  (`env`/`Lead`/`Stage` only exist at `odoo shell` runtime, and the
  idempotent-backdate re-run logic in particular can only be proven by
  actually running the script twice against a live database).
- Re-confirmed `docker` is still not on PATH in this session's shell.

### Files changed

- `scripts/create-gate3-fixtures.sh` — FX7 block added (qualify/draft/
  approve/claim/finalize/backdate), summary print extended.
- `scripts/gate3-workflow4-test-payloads.md` — one note added under
  "## Notes".
- This file, appended only.

No file inside `odoo/addons/ggd_crm/**` was touched (only read, for the
write()-guard check above). No commit was made, no branch changed. Docker
was not run, per instruction.

### Process note (recurring)

`.git/index.lock` is present again in the repository as of this pass (it
had cleared between the previous two handoff entries). Same as before: no
git write command was run here, nothing was touched, and this is only
reported in case it signals Codex or another participant mid-operation on
the shared repository.

---

## FX7 live fixture run — 26 August 2026 (orchestrator)

The idempotent fixture script completed against local Odoo. FX1–FX6B were
reported as `EXISTS`, and FX7 was created with its real Odoo ID:

```text
CREATED  FX7_STALE_FOLLOWUP     id=437    [GGD-GATE3-FIXTURE] FX7 -- Stale Confirmed Send, For Follow-Up Queue Test (Ostsee Fictional Feinmechanik OHG)
```

Its confirmed-send timestamp was backdated by eight days as designed. No n8n
workflow ran and no email was sent.

---

## Standby — 26 August 2026 (Odoo lane)

Status: BLOCKED: DOCKER_OFF (unchanged in this session's shell).

Acknowledging the standing order: this session will never attempt to
export, read, or copy n8n credential material, in any form (export via
n8n's UI/API, database reads of the credentials table, or otherwise). This
was never in the Odoo lane's scope and stays that way.

Checked as requested: no lingering git process from this session (only
`ps -ef` was run to look, plus earlier read-only `git status`/`git diff
--stat` calls — no git write command was ever run here) and
`.git/index.lock` is currently absent.

Per the orchestrator: FX7 is accepted, Codex will re-run
`scripts/create-gate3-fixtures.sh` and execute Gate 3. This session is on
standby and starting no new work — next expected task is fixing a
confirmed Odoo-side defect if Gate 3 surfaces one.

---

## Offline pre-flight review of addon 19.0.1.6.0 — 26 August 2026

Status: BLOCKED: DOCKER_OFF for live tests, but the addon now has a real
static pre-flight behind it. Requested by Kaan directly ("check the files").

### Attempt to run the 102 tests without Docker — not possible

Tried to build a real Odoo 19 test environment in the Claude cloud container
so the 102 tests could run without Docker. Result: **not possible.**
PostgreSQL 16.13 starts fine there and `github.com` is reachable (Odoo 19.0
source cloned successfully, confirmed `version_info = (19, 0, 0, FINAL, 0)`),
but **PyPI is not reachable from that container** (`pip install
psycopg2-binary` -> "No matching distribution found", i.e. no index), so
Odoo's Python dependencies cannot be installed and Odoo cannot boot. Live
test execution still requires Kaan's Docker.

### What WAS verified, and how

Static checks against the addon itself:

- **102 test methods** in `tests/test_crm_lead.py` — matches the 102 target
  exactly. Single class `TestGgdOutreachApproval(TransactionCase)`, tagged
  `post_install, -at_install`.
- All addon `.py` files parse (`ast.parse`); `views/crm_lead_views.xml` is
  well-formed XML.
- **Every public model method has test references**: `ggd_claim_send_key`
  (31), `write` (61), `create` (16), `action_ggd_approve_outreach` (15),
  `ggd_finalize_send` (13), `ggd_record_reply` (9), `ggd_prepare_draft` (6),
  `ggd_queue_follow_up` (5), `ggd_record_bounce` (4),
  `ggd_find_reply_candidates` (4), `ggd_record_automation_error` (4),
  `action_ggd_release_failed_send_claim` (4), `ggd_apply_qualification` (3),
  `action_ggd_revoke_outreach` (3), `ggd_queue_unmatched_inbound` (2),
  `action_ggd_resolve_automation_review` (2). Private helpers are covered
  indirectly through those public entry points.
- 53 of 54 `ggd_*` fields appear in the form view. The one absent is
  `ggd_last_follow_up_queue_key` (internal dedup key) — deliberate, not a
  defect, though exposing it read-only would help follow-up auditing.
- View syntax is Odoo 17+/19 style: `invisible="..."` expressions, no
  removed `attrs=`/`states=`, no renamed `<tree>` element. **No view-level
  upgrade breaker.**

Cross-checked the addon's external API assumptions against the **real Odoo
19.0 source** (the clone above), which is what usually breaks a major-version
upgrade. All six confirmed present/compatible:

| Assumption | Odoo 19.0 source | Result |
| --- | --- | --- |
| `email_normalized` on `crm.lead` (used in `ggd_find_reply_candidates` domain) | `addons/crm/models/crm_lead.py:186` | OK |
| view `crm.crm_lead_view_form` (inherit target) | `addons/crm/views/crm_lead_views.xml:3` | OK |
| `crm.stage.is_won` (used in `ggd_queue_follow_up`) | `addons/crm/models/crm_stage.py:27` | OK |
| `mail.mail_activity_data_todo` (activity xmlid) | `addons/mail/data/mail_activity_type_data.xml:24` | OK |
| `check_access(operation)` (Odoo 18+ merged API) | `odoo/orm/models.py:4100`; legacy `check_access_rights`/`check_access_rule` still exist at 4162/4176 | OK — `_ggd_check_claim_access`'s getattr shim resolves to the new API and its legacy fallback remains valid |
| `activity_schedule(act_type_xmlid, date_deadline, summary, note, **act_values)` | `addons/mail/models/mail_activity_mixin.py:357` | OK — the `user_id=` kwarg the addon passes is accepted via `**act_values` |

### Defects found

**None blocking.** No incorrect logic, no Odoo 19 incompatibility, and no
missing test coverage was identified in this pass. One cosmetic observation
only (`ggd_last_follow_up_queue_key` not surfaced in the view).

This is not a substitute for the live run — a static pass cannot catch
registry/ORM-level failures, migration issues on the existing `ggd`
database, or genuine test assertion failures. It does mean the most common
class of major-version upgrade breakage has been ruled out in advance, so
`-u ggd_crm` has a good chance of succeeding on the first attempt.

### Files changed

This file only. Nothing in `odoo/addons/ggd_crm/**` was modified — this was
a read-only review. No commit, no branch change, no Docker, no email, no
workflow touched.

---

## GATE 1 RESULT — PASSED — 26 August 2026, 16:35 Europe/Berlin

Status: **ODOO_GREEN: 102/102**

Executed by Kaan in his macOS Terminal (this Claude Code session's own shell
has no Docker access; that limitation is unchanged and is why the run was
handed to him). Full console output was pasted back to this session and is
summarised faithfully below.

### Commands run

```
cd ~/Desktop/"GGD -Sales-System "
docker compose up -d
./scripts/run-addon-tests.sh
```

### Container state

All four containers up before the test run:

```
✔ Container ggd-sales-system-odoo-1     Running
✔ Container ggd-sales-system-n8n-db-1   Healthy
✔ Container ggd-sales-system-n8n-1      Running
✔ Container ggd-sales-system-odoo-db-1  Healthy
```

### Test result

```
2026-08-26 16:35:28,778 464 INFO ggd odoo.service.server: 102 post-tests in 1.57s, 6425 queries
2026-08-26 16:35:28,778 464 INFO ggd odoo.tests.stats: ggd_crm: 104 tests 1.56s 6425 queries
2026-08-26 16:35:28,778 464 INFO ggd odoo.tests.result: 0 failed, 0 error(s) of 102 tests when loading database 'ggd'
```

**0 failed, 0 errors, 102 tests.** Odoo server version reported as
`19.0-20260810`.

### Upgrade evidence

The addon was upgraded, not merely loaded from cache:

```
ALLOW access to module.button_upgrade on ['Germany Growth Desk CRM Controls']
loading 45 modules...
Loading module ggd_crm (42/45)
module ggd_crm: creating or updating database tables
loading ggd_crm/views/crm_lead_views.xml
Module ggd_crm loaded in 0.10s, 95 queries (+95 other)
verifying fields for every extended model
Registry loaded in 1.114s
```

No ORM errors, no view-parse errors, no field-verification errors. This
confirms the offline pre-flight in the previous entry: the Odoo 19 API
assumptions (`email_normalized`, `crm.crm_lead_view_form`, `crm.stage.is_won`,
`mail.mail_activity_data_todo`, `check_access()`, `activity_schedule()`) all
held against the live 19.0 registry, and the modern view syntax parsed
without incident.

### Two benign log observations, neither a defect

1. `odoo.tests.stats: ggd_crm: 104 tests` vs
   `odoo.tests.result: ... of 102 tests`. The `stats` line is Odoo's
   per-module aggregate and counts more entries than the authoritative
   result line. The result line — the one Gate 1 is defined against —
   reports 102 tests, 0 failed, 0 errors. No test is missing or
   double-counted in a way that affects the gate.
2. A `WARNING ... no translation language detected, skipping translation`
   with a stack trace, raised from `_ggd_check_recipient_ready`
   (crm_lead.py:426) during
   `test_approval_requires_a_valid_recipient`. This is standard Odoo
   logging noise: `_()` was called in a test context with no active
   language. The test itself passed. No code change is warranted; changing
   it would mean removing translation from a user-facing error message,
   which would be a regression, not a fix.

### Remaining Gate 1 item

The gate text also requires the *installed addon version* to be confirmed.
The test log proves `ggd_crm` was upgraded and loaded but does not print its
version string. A one-line confirmation of `ir_module_module.latest_version`
for `ggd_crm` has been requested from Kaan and will be appended here. The
manifest on disk declares `19.0.1.6.0` and the upgrade ran against that
manifest, so this is expected to be a formality.

### Files changed

None. This entry is a result record only. No addon file was modified for
Gate 1 — the suite passed as written.

### Gate 1 version confirmation — COMPLETE

Run 26 August 2026 16:37 Europe/Berlin:

```
echo "print(env['ir.module.module'].search([('name','=','ggd_crm')]).latest_version)" \
  | docker compose exec -T odoo /bin/bash -lc 'odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http'
=> 19.0.1.6.0
```

**Installed addon version is `19.0.1.6.0`, matching the manifest.** Combined
with `0 failed, 0 error(s) of 102 tests`, both halves of Gate 1 are now
satisfied: version confirmed AND 102/102 passing. Gate 1 is closed from the
Odoo lane's side; Codex reviews.

---

## Gate 3 fixtures — CONFIRMED PRESENT, 26 August 2026 16:37 Europe/Berlin

`./scripts/create-gate3-fixtures.sh` run by Kaan. All eight records report
EXISTS (they had already been created by an earlier run), so this run created
nothing and changed nothing.

| Fixture | Odoo id | Purpose |
| --- | ---: | --- |
| FX1_PENDING | **430** | Workflow 1 — pending qualification |
| FX2_QUALIFIED_READY | **431** | Workflow 2 — qualified, ready to draft |
| FX3_DO_NOT_CONTACT | **432** | suppression gate, all workflows |
| FX4_APPROVED_DRAFT | **433** | reserved for Gate 4 (recipient still `.invalid`) |
| FX5_SENT_SYNTHETIC | **434** | Workflow 4 — reply match + bounce |
| FX6A_AMBIGUOUS | **435** | Workflow 4 — ambiguous match pair |
| FX6B_AMBIGUOUS | **436** | Workflow 4 — ambiguous match pair |
| FX7_STALE_FOLLOWUP | **437** | Workflow 5 — stale confirmed send |

Key values for the workflow test payloads:

```
FX5 message-id: <gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>
FX5 send key:   434:b448fda8cf6d41949a36f00f916353ec
FX7 message-id: <gate3-fixture-fx7-001@ggd-gate3-fixture.invalid>
FX7 send key:   437:1c4f7d0cacad4503b796e16b67bfea02
FX6 shared ambiguous email: fx6-ambiguous@ggd-gate3-fixture.invalid
FX7 ggd_send_confirmed_at: 2026-08-18 13:41:29.898594  (8 days back — stale, as designed)
```

### What this run independently proves

This was an all-EXISTS re-run, which is stronger evidence than a first run:

1. **The idempotency guard works.** Eight fixtures, zero duplicates created,
   zero errors, on a database that already contained them. The
   `get_or_create` name-lookup and FX7's backdate-skip condition both held.
2. **The two orchestrator-reported defects are genuinely fixed, on real
   committed records.** Both send keys carry the required
   `<id>:<approved_draft_version>` shape (`434:b448fda8…`,
   `437:1c4f7d0c…`). If the shape were wrong,
   `_ggd_check_send_key_matches_approved_draft` would have raised and the
   original run could never have produced these records.
3. **The real send path works outside the test transaction.** The 102 unit
   tests run in `TransactionCase` and roll back, so nothing they exercise is
   ever committed. FX5 and FX7 reached `ggd_send_confirmed_at` through
   `ggd_claim_send_key` → `ggd_finalize_send` and were **committed** to the
   `ggd` database. That is the first live, durable proof of the claim →
   finalize path. No SMTP was involved and no email was sent.
4. **FX7's backdating landed correctly**: `2026-08-18 13:41:29`, i.e. 8 days
   before the run, comfortably past both the 7-day cutoff in Workflow 5's
   candidate query and `ggd_queue_follow_up()`'s own guard.

### Odoo-side methods still unproven on committed records

The unit tests cover these, but only inside rolled-back transactions; no
committed-record exercise exists yet for:
`ggd_record_reply`, `ggd_record_bounce`, `ggd_queue_follow_up`,
`ggd_find_reply_candidates`, `ggd_queue_unmatched_inbound`.

These are exactly the methods Workflows 4 and 5 call. They will be exercised
for real during Gate 3, or sooner via a standalone Odoo-side smoke script if
one is requested.

### Files changed

None. Result record only.

---

## Odoo method smoke test — PASSED — 26 August 2026, 16:46 Europe/Berlin

New file: `scripts/smoke-test-odoo-methods.sh` (Odoo lane; creates its own
throwaway records, archives them, never touches FX1-FX7, sends no email).

Purpose: the 102 unit tests run in `TransactionCase` and roll back, so the
five methods Workflows 4 and 5 depend on had never executed against a
committed record. This script closes that gap.

```
SMOKE RESULT: 27 passed, 0 failed
```

Run id `20260826164652`, throwaway domain `ggd-smoke-20260826164652.invalid`,
13 records created and all 13 archived at the end. Nothing was deleted.

| Group | Method | Checks | Result |
| --- | --- | ---: | --- |
| A | `ggd_find_reply_candidates` | 4 | all pass |
| B | `ggd_record_reply` | 8 | all pass |
| C | `ggd_record_bounce` | 4 | all pass |
| D | `ggd_queue_follow_up` | 6 | all pass |
| E | `ggd_queue_unmatched_inbound` | 4 | all pass |
| — | cleanup/archive | 1 | pass |

### The checks that matter most, all green

These target the specific failure classes this project has been bitten by
before (silent duplicates, guards that report success while doing nothing):

- **A3** a shared sender address returns TWO candidates, so an ambiguous
  reply cannot be auto-applied to the wrong opportunity.
- **A4** an unknown sender returns `match_type: none` rather than a wrong
  match.
- **B2** a replayed Message-ID is a genuine no-op — prior analysis untouched.
- **B3** a late-arriving OLDER reply does not overwrite newer state.
- **B5** unsubscribe both sets `ggd_do_not_contact` and discards the drafted
  outbound response.
- **C2** a bounce whose Message-ID matches nothing is refused rather than
  attached to the wrong record.
- **D3** a repeat follow-up run creates ZERO extra activities (dedup proven
  by counting `mail.activity` rows, not by trusting the return value).
- **D4/D5** suppression and an existing reply each block follow-up.
- **E2** the same inbound Message-ID twice creates ONE review record.

### Standing of the Odoo lane

With Gate 1 green (`19.0.1.6.0`, 102/102) and this smoke test green, every
addon method that the automation layer calls is now proven **both** in
isolated unit tests **and** against real committed records. The remaining
unproven surface in the product is n8n: workflow import, credential binding,
and live execution. No Odoo-side defect is outstanding.

### Files changed

- `scripts/smoke-test-odoo-methods.sh` (new)
- This file, appended.

No change to `odoo/addons/ggd_crm/**`. No commit, no branch change, no email,
no workflow file touched.

---

## Pre-Gate-2 workflow pre-flight (read-only) — 26 August 2026

`./scripts/validate-project.sh` run from this session's shell (Node v22.23.2
is available here; Docker still is not, so Compose validation was skipped as
designed).

```
26 passed, 0 failed    (workflow export/decision suite)
19 passed, 0 failed    (legacy Workflow 4 matcher regressions)
.env is ignored: OK
Project validation passed.
```

Notable passing assertions, quoted because they are safety-relevant:
`Only Workflow 3 contains an email-send node`;
`Workflow 3 cannot draft or call an LLM after human approval`;
`Workflow 3 fails closed at claim and records uncertain SMTP or finalize results`;
`All workflow credential references remain explicit placeholders`.

### Read-only inspection of the six exports

No workflow file was modified. Structural facts for the import step:

| File | Workflow name | active | nodes | errorWorkflow |
| --- | --- | --- | ---: | --- |
| GGD-00 | GGD-00 Shared automation error handler | false | 5 | none |
| GGD-01 | GGD-01 Lead qualification | false | 11 | none |
| GGD-02 | GGD-02 Draft and approval queue | false | 10 | none |
| GGD-03 | GGD-03 Approved reviewed draft send | false | 15 | none |
| GGD-04 | GGD-04 Reply and bounce intake | false | 15 | none |
| GGD-05 | GGD-05 Daily follow-up review queue | false | 10 | none |

**All six are `active: false` in the export** — importing them cannot start
anything.

Credential references by workflow (names only; no credential value was read,
exported, or copied, per the standing order):

- `httpHeaderAuth: Odoo JSON-2 bearer token` — all six
- `anthropicApi: Anthropic account` — 01, 02, 04, 05
- `smtp: Zoho SMTP` — **03 only**
- `imap: Zoho IMAP` — **04 only**

### One thing that must not be skipped at import

`errorWorkflow` is **null in all six exports**. Setting Workflow 00 as the
error workflow for 01-05 is a manual post-import step in the n8n UI
(workflows/README.md step 3). It cannot be inherited from the JSON. Given
that PROJECT-STATUS.md records the error-handling layer as historically the
least-proven part of the system, and records a past incident where a
workflow read `active: false` while still firing, this step deserves explicit
verification after import rather than assumption.

### Files changed

This file only. `workflows/**` and `tests/workflows/**` were read but not
modified.

---

## Re-synced with actual project state — 26 August 2026

Kaan pointed out that I was advising from the tracked files rather than the
documented live state. He was right. Correcting the record:

**My error.** I inspected `workflows/*.json`, saw every credential id as
`REPLACE_WITH_*`, and told Kaan he had ~15 nodes to bind. Those placeholders
are *deliberate and permanent* in the tracked exports — that is the discipline
that keeps credential material out of Git, and Fable's review item 9 even
proposes asserting it in the test suite. The tracked file therefore says
nothing about live binding state. Per `NEXT-ACTIONS.txt` and
`docs/handoffs/FABLE-5.md`, Workflows 00-05 were already imported into
n8n 2.34.6 with **all credentials bound**. My binding advice was unnecessary
work and is withdrawn. Lesson, and it is the same one defect 12 taught: a
file is not the running system.

**Actual state, per NEXT-ACTIONS.txt and FABLE-5.md (26 August):**

- Codex exhausted its token budget; Fable 5 was reassigned from offline
  reviewer to orchestrator + live executor for the non-sending workflows.
- Gate 3 steps 1, 1b and 2 PASS. Steps 3-9 outstanding.
- Workflow 1 proven end to end against `https://www.germanygrowthdesk.com`:
  page fetched, `claude-sonnet-5` called, Odoo written, and critically
  `ggd_outreach_approved` stayed False (PLAN control 2) with low confidence
  (0.05) routing lead 430 to `review` rather than `ready`.
- Re-running Workflow 1 did not re-select the parked record — the
  `ggd_automation_needs_review = false` selector exclusion holds live.
- Two defects found and fixed by Fable today: **11** the error workflow was
  assigned but inactive, so every failure went unrecorded (GGD-00 now
  published); **12** the source-URL guard referenced the WHATWG `URL` global,
  which n8n's bare `vm` sandbox does not provide, so it rejected every URL
  including valid ones (rewritten regex-based, two sandbox-fidelity tests
  added, validation now 26/26).
- GGD-03 remains off and its execution is denied in `.claude/settings.json`.

**Nothing in the above requires an Odoo-side change.** No defect has been
attributed to `ggd_crm` at any point in Gate 3.

### New file: scripts/show-gate3-fixture-state.sh

Read-only state dump of FX1-FX7 plus any `Manual inbound review:` records
Workflow 4 creates. Prints qualification, draft, approval, send, reply,
follow-up and review-flag state per fixture, with activity and chatter counts.

Intended use: run it immediately before and immediately after each Gate 3
workflow step, and diff the two. This matters for this project specifically —
its recurring failure mode is a control that reports success while doing
nothing (defects 1, 2, 8, 10, 11). Reading the durable Odoo record is the
only reliable check; an n8n execution marked "success" has repeatedly not
meant the work happened.

It writes nothing, commits nothing, sends nothing, and does not touch n8n. It
is safe to run while a workflow is executing.

Verified: `bash -n` clean, embedded Python parses. Not yet executed (this
session still has no Docker).

### Files changed

- `scripts/show-gate3-fixture-state.sh` (new)
- This file, appended.

No change to `odoo/addons/ggd_crm/**`, `workflows/**`, or `tests/workflows/**`.

---

## Gate 3 steps 3, 5 and 7 — PASS — 26 August 2026, 17:00 Europe/Berlin

Executed by Kaan via CLI (`n8n execute`), evidence read back from Odoo with
`scripts/show-gate3-fixture-state.sh` before and after.

### Step 3 — Workflow 2 draft on FX2 (431): PASS (already satisfied)

The G02DRFT run selected **nothing** — `Select qualified leads without
drafts` returned `[]`. That is the correct result, because FX2 already
carried a completed draft from an earlier successful run:

```
id=431  DRAFT status=ready  version=172ac047e…
        subject=Exploring a Potential Fit for…
        APPROVAL approved=no   basis=-   do_not_contact=no
```

The subject is model-written, not the fixture placeholder, so Workflow 2 did
genuinely run at some point after the `claude-sonnet-5` migration. Step 3's
acceptance conditions are met: **one stored draft, `draft_status = ready`,
and outreach still NOT approved.** The empty selection on this run is itself
a second useful result — the "qualified leads *without* drafts" selector
correctly refuses to redraft a record that already has one, the same
don't-redo-work property proven for Workflow 1's parked records.

Kaan still owes the human step: open 431 in Odoo and READ the draft. Do not
approve it.

### Step 5 — Workflow 5 queues one follow-up on FX7 (437): PASS

Already satisfied before this run, at 16:11:32:

```
id=437  FOLLOWUP queue_key=437:437:1c4f7d0caca…  queued_at=2026-08-26 16:11:32
        activities=1
```

Exactly one activity. The selector picked FX7 and only FX7 — FX5 (434), whose
send is from today, was correctly excluded by the 7-day boundary.

### Step 7 — Workflow 5 dedup on re-run: PASS

This is the strong result. The 17:00 run executed the **full** chain — select
→ exclude-replies → `claude-sonnet-5` draft → validate → record — and the
final node returned:

```
"Create one deduplicated Odoo review activity": { "json": false }
```

`false`, not an error. And Odoo after the run still shows `activities=1` and
`queued_at=2026-08-26 16:11:32` — the *original* timestamp, unchanged.

Note what this proves that a return value alone would not: the workflow did
all the expensive work (it really did call the model and produce a fresh
follow-up draft), then `ggd_queue_follow_up` recognised the queue key was
already claimed and declined to create a second activity. Dedup is enforced
in Odoo at the moment of writing, not by the workflow deciding to skip. That
is the correct place for it.

### Finding: redundant lead id in the follow-up queue key — COSMETIC, DO NOT FIX

Observed key: `437:437:1c4f7d0cacad4503b796e16b67bfea02`

Cause, `crm_lead.py:1275`:

```python
confirmed_key = state.get("ggd_last_confirmed_send_key")   # already "437:1c4f7d0c…"
queue_key = "%s:%s" % (self.id, confirmed_key)             # -> "437:437:1c4f7d0c…"
```

The send key already begins with the lead id, so prefixing the id again
duplicates it.

**Assessment: cosmetic only, and it should be left alone.** The key is still
unique per lead per confirmed send, and still deterministic, which is all the
dedup contract requires — proven live by step 7 above. Changing the format
would be a net negative: every record already carrying an old-format key
would stop matching the newly-computed key, so the next Workflow 5 run would
create a **second** activity on each of them. That trades a harmless
duplicated substring for a real duplicate-work bug, in the exact area this
project has been bitten before. Recommend leaving it and noting it here so
nobody "tidies" it later without understanding the migration cost. If it is
ever changed, it needs a migration that rewrites existing
`ggd_last_follow_up_queue_key` values in the same transaction.

### Housekeeping note

The state dump lists one unmatched-inbound record, `id=566 "Manual inbound
review: Smoke: subject of an…"`. That is a leftover from this session's own
smoke test (`scripts/smoke-test-odoo-methods.sh`), already archived
(`active=False`) by the script. It cannot interfere with Gate 3: its
Message-ID and sender both carry a per-run unique `.invalid` domain, so
neither `ggd_queue_unmatched_inbound`'s dedup search nor
`ggd_find_reply_candidates` can collide with the Gate 3 payloads. Harmless,
but worth knowing why it is there.

### Gate 3 status after this run

| Step | Description | Status |
| --- | --- | --- |
| 1, 1b, 2 | Workflow 1 error path, error-handler wiring, happy path | PASS (Fable) |
| 3 | Workflow 2 draft on FX2, no approval | **PASS** |
| 4 | Workflow 4 scenarios 1-4 | outstanding |
| 5 | Workflow 5 queues one follow-up | **PASS** |
| 6 | Workflow 4 scenarios 5-6 + negative bounce | outstanding |
| 7 | Workflow 5 dedup re-run | **PASS** |
| 8 | Error-handler production proof (scheduled activation) | outstanding |
| 9 | Re-export, graph match, revalidate | outstanding |

No Odoo-side defect. No email sent. GGD-03 untouched and still denied.

### Files changed

This file only.

---

## DEFECT 13 diagnosed and FIXED — 27 August 2026

Status: **ODOO_GREEN pending re-run at 19.0.1.7.0** (was 102/102 at
19.0.1.6.0; suite is now 103 tests).

### The defect

Workflow 2's `Store immutable draft for human approval` node reported

```
NodeOperationError: Response body is not valid JSON. Change "Response Format" to "Text"
url: http://odoo:8069/json/2/crm.lead/ggd_prepare_draft
```

but the state dump taken 7 seconds later proved **Odoo had stored and
committed the draft** (FX2/431 went `draft=empty` -> `draft=ready`, version
`172ac047e…`, model-written subject, chatter 2 -> 3).

This is the inverse of defects 1, 8, 10 and 11. Those reported success while
doing nothing. This reports failure having done the work — worse in one
specific way: a retry calls `ggd_prepare_draft` again, mints a **second**
draft version and silently discards the one a human may already have read.
It also invoked the error workflow, which crashed n8n internally with
`TypeError: Cannot read properties of undefined (reading 'run')`.

### Root cause, established by measurement not inference

`scripts/diagnose-json2-response.sh` (new) reproduces Odoo's own serializer
for every method the workflows call. Result:

```
OK  ggd_prepare_draft (str)          Content-Length=34   actual_bytes=34   "b5ba26f6…"
OK  ggd_claim_send_key (bool)        Content-Length=4    actual_bytes=4    true
OK  ggd_finalize_send (bool)         Content-Length=4    actual_bytes=4    true
OK  ggd_find_reply_candidates (dict) Content-Length=226  actual_bytes=226  {...}
```

All return values are pure ASCII, so the Content-Length hypothesis
(`odoo/http.py:2087` sets Content-Length in characters, not bytes) is
**excluded** as the cause here.

What remains, and matches every observation: **n8n's HTTP Request node
refuses a top-level JSON scalar string.** `ggd_prepare_draft` was the only
workflow-called method returning one. Every other method returns bool, int,
dict or list — and Workflow 5's node returned bare `false` in the same run
without complaint, which rules out "n8n rejects all scalars".

A bare string is legal JSON (RFC 8259 permits scalars at the top level), so
Odoo is not wrong. The client is strict. The fix belongs on our side anyway,
because we control it and because a dict is the better contract.

### Fix applied

`odoo/addons/ggd_crm/models/crm_lead.py` — `ggd_prepare_draft` now returns
`{"draft_version": <hex>}` instead of the bare hex string, with the full
reasoning recorded in its docstring.

Chosen over the alternative (setting that node's Response Format to "text")
deliberately: a node-level setting is invisible to the test suite and would
**not survive the Gate 3 step 9 re-import**, reintroducing the defect
silently. Returning a dict fixes it once, for every client, and is provable
by the addon's own tests.

Blast radius checked before changing anything: the workflow does **not**
consume the return value (`Store immutable draft…` is Workflow 2's terminal
node), and no script uses it. Exactly one test asserted it.

- `tests/test_crm_lead.py` — `test_prepare_draft_revokes_old_approval_and_returns_new_version`
  updated to read `result["draft_version"]`.
- **New test** `test_prepare_draft_returns_a_json_object_not_a_bare_string`
  asserts the return is a dict with exactly the `draft_version` key. This is
  a deliberate regression guard: this project's recurring failure is an
  invariant that nobody asserted, so restoring the bare string later will now
  fail the suite instead of silently breaking Workflow 2 again.
- **Test count is therefore 103, not 102.** Every document that cites 102
  (`docs/FOUR-AGENT-EXECUTION-PLAN.md`, `NEXT-ACTIONS.txt`,
  `docs/PROJECT-STATUS.md`, `workflows/README.md`) needs updating by whoever
  owns them; I did not edit those files.
- `__manifest__.py` — version bumped **19.0.1.6.0 -> 19.0.1.7.0**. Shipping
  changed code under an unchanged version number would make the "19.0.1.6.0
  proven" record false. The gate definition's "19.0.1.6.0" therefore needs
  re-pointing to 19.0.1.7.0.

`./scripts/validate-project.sh` still passes (26/26 workflow, 19/19 matcher).

### Second finding: latent, upstream, NOT acted on

The diagnostic also showed:

```
MISMATCH  UWG s7 refusal (contains non-ASCII)  Content-Length=275  actual_bytes=278
OK        plain ASCII refusal                  Content-Length=75   actual_bytes=75
```

`odoo/http.py:2087` computes Content-Length from the character count while
the body is UTF-8 bytes, so any response containing non-ASCII — such as this
addon's UWG §7 refusal, which contains `§` and an em dash — carries a
Content-Length three bytes short.

**I did not change anything for this, and I believe it is masked in
practice.** Odoo passes the string to `werkzeug.Response`, whose `set_data()`
re-encodes and overwrites Content-Length with the correct byte count, and the
explicit header is set before that call. So the wrong value is computed and
then corrected. Worth recording because if that werkzeug behaviour ever
changes, the addon's most important safety refusal would arrive truncated and
unparseable — the failure would still be closed (the send would not happen)
but the *reason* would be lost, which defeats the error handler's purpose.
If anyone wants belt-and-braces, making the addon's error strings ASCII-only
would sidestep it entirely; I judged that not worth degrading the legal
wording on a masked bug.

### What Kaan must run next

```
./scripts/run-addon-tests.sh            # expect 103 tests, 0 failed, 0 errors
docker exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5699 \
  ggd-sales-system-n8n-1 n8n execute --id G02DRFT20260826
```

Workflow 2 will select nothing while FX2 still holds a draft, so proving the
fix needs a lead that is qualified-ready with no draft. Clearing FX2's draft
fields is the smallest way to produce one.

### Files changed

- `odoo/addons/ggd_crm/models/crm_lead.py`
- `odoo/addons/ggd_crm/tests/test_crm_lead.py`
- `odoo/addons/ggd_crm/__manifest__.py`
- `scripts/diagnose-json2-response.sh` (new; label corrected after the fix)

No workflow file, no shared status document, no commit, no branch change.

---

## Defect 13 fix VERIFIED in the addon — 27 August 2026, 08:38 Europe/Berlin

`./scripts/run-addon-tests.sh` after the fix:

```
2026-08-27 08:38:14,360 INFO ggd odoo.service.server: 103 post-tests in 1.48s, 6477 queries
2026-08-27 08:38:14,360 INFO ggd odoo.tests.result: 0 failed, 0 error(s) of 103 tests when loading database 'ggd'
```

The upgrade ran (`module.button_upgrade` -> `creating or updating database
tables` -> views reloaded -> `verifying fields for every extended model`), so
addon **19.0.1.7.0** is installed and green.

Both affected tests are visible in the run and passed:

```
Starting TestGgdOutreachApproval.test_prepare_draft_returns_a_json_object_not_a_bare_string ...
Starting TestGgdOutreachApproval.test_prepare_draft_revokes_old_approval_and_returns_new_version ...
```

**Status: ODOO_GREEN: 103/103 at 19.0.1.7.0.** The Odoo side of defect 13 is
closed. What is NOT yet proven is the end-to-end effect: that Workflow 2's
`Store immutable draft for human approval` node now returns GREEN instead of
`Response body is not valid JSON`. That needs one live run and is the only
outstanding item on this defect.

Test-count history for anyone reconciling the documents:
102 (19.0.1.6.0, Gate 1) -> 103 (19.0.1.7.0, +1 regression guard).

### Files changed

This file only.

---

## OPERATIONAL FINDING: the Odoo API key defaults to a 1-DAY expiry — 27 August 2026

Not an addon defect, but it stopped all Gate 3 work this morning and will
recur, so it is recorded here.

### Symptom

Every Workflow run failed at its FIRST Odoo node:

```
401 Unauthorized: Invalid apikey
node: "Select qualified leads without drafts"
```

It had worked at 17:00 the previous evening.

### Confirmed cause

`scripts/check-odoo-api-keys.sh` (new, read-only, metadata only — key values
are hashed and unreadable by design) reported:

```
Server time now: 2026-08-27 08:50:53 UTC
  NO API KEYS EXIST AT ALL.
```

Not "expired" — **gone**. Verified against the Odoo 19 source:

- `res.users.apikeys._check_apikey_credentials` accepts a key only when
  `expiration_date IS NULL OR expiration_date >= now()`.
- An `@api.autovacuum` job then DELETES rows where
  `expiration_date IS NOT NULL AND expiration_date < now()`.

So an expired key first stops authenticating, then disappears entirely.

### Root cause: the wizard's default

`res.users.apikeys.description` (res_users.py:1776-1780):

```python
duration = fields.Selection(
    selection='_selection_duration', string='Duration', required=True,
    default=lambda self: self._selection_duration()[0][0]
)
```

`_selection_duration()` returns `[('1','1 Day'), ('7','1 Week'), ...]`, so the
**default selection is "1 Day"**. Anyone who accepts the default gets a key
that dies overnight. That is exactly what happened.

Two further facts from the same method, which matter for the fix:

1. The infinite option is labelled **"Persistent Key"** (magic value `'0'`),
   NOT "Never". I initially told Kaan to look for "Never" — that label does
   not exist, and the wrong label likely cost him time. Corrected.
2. `persistent_duration` is only appended **when `self.env.is_system()`** —
   i.e. only a Settings-admin sees "Persistent Key" at all. A non-admin is
   capped at `max(group.api_key_duration)` and
   `_check_expiration_date` rejects anything longer, so a non-admin
   **cannot** create a long-lived key even via "Custom Date".

### Consequence for the project

The whole automation layer silently depends on a credential whose creation
wizard defaults to 24 hours. This deserves a line in the operations
documentation (Codex-owned, not edited here): the Odoo API key must be
created by an administrator with **Persistent Key**, and a dead key must be
recognised by its signature — a 401 `Invalid apikey` at the first Odoo node
of every workflow.

**The failure mode itself was safe.** Odoo refused, n8n stopped at node 1,
nothing was written and nothing was sent. Credential failure is fail-closed;
that had never been observed before today and is now evidenced.

### Unrelated observation

Between the 08:50 and 08:57 runs of the key check, the Odoo registry went
from **45 modules to 76**. Something installed roughly 31 additional modules
in that window. Not harmful in itself, but it changes the environment mid-test
and should be understood before Gate 5 sign-off, since the addon's Gate 1
evidence was gathered on a 45-module registry.

### Files changed

- `scripts/check-odoo-api-keys.sh` (new)
- This file.


---

## DEFECT 13 - CLOSED 27 August 2026 09:16 UTC

**Symptom.** Workflow 2's node "Store immutable draft for human approval"
failed with `Response body is not valid JSON. Change "Response Format" to
"Text"` while Odoo had in fact stored the draft. Every other Odoo node in
every other workflow was green against the same server and the same
credential.

**Root cause (two layers, both real).**

1. `ggd_prepare_draft` returned a bare string (the draft version). Odoo
   serialises that as a top-level JSON *string*: `"d434f6ad14a7...".`
   n8n's HTTP Request node v4.3 in autodetect mode parses the body once,
   sees the result is still a JavaScript string, and parses it a second
   time (`HttpRequestV3.node.ts:1131`). `JSON.parse("d434f6ad14a7...")` on
   the raw hex throws. Every other addon method returns a dict, list, bool
   or int, so none of them hit the second parse - Workflow 5's node
   returned a bare `false` without complaint. `ggd_prepare_draft` was the
   only method in the system returning a top-level JSON string.
2. The fix (return `{"draft_version": version}`) was written at 08:27 and
   verified by 103 passing tests, but the long-running Odoo HTTP worker had
   started at 08:25 and never re-imported it. `-u ggd_crm` reloads the
   registry from modules already in `sys.modules`; it does not re-read
   changed `.py` files, and `scripts/start-odoo.sh` runs the server without
   `--dev=reload`. The tests and the live endpoint were running different
   code, which is why the fix appeared not to work.

**How it was proved, not guessed.** `scripts/diagnose-json2-response.sh`
reproduced Odoo's serializer inside `odoo shell` - a fresh process - so it
could only ever describe the source code, never the live worker. The second
diagnostic, `scripts/diagnose-defect13-wire.sh`, talks to the live worker
over real HTTP from inside the odoo container and prints status, headers,
declared Content-Length, actual byte count and a repr of the body. It
returned `b'"d434f6ad14a746318b6ffa442d61d13e"'` - the old bare string -
which settled both layers at once. It also ruled out truncation
(Content-Length matched the byte count on all four calls), compression
(gzip and identity behaved identically) and non-ASCII payloads (German
umlauts made no difference).

**Resolution.** `docker compose restart odoo`, then re-ran Workflow 2. Full
green run at 09:16:41 UTC: the node returned
`{"draft_version": "0854f42851674d728fc28dfd9e9bd8a7"}` as a JSON object,
every node reported `executionStatus: "success"`, and the recurring
`Cannot read properties of undefined (reading 'run')` error-workflow crash
did not appear because there was no error to hand off.

**Operational consequence worth carrying forward.** Any change to
`odoo/addons/ggd_crm/**` python requires `docker compose restart odoo`
before the running system reflects it. Passing tests alone do not prove the
live endpoint changed. This should be stated wherever the addon test
procedure is documented (Codex-owned files; not edited from this lane).

## Defect found in passing: clearing a draft left an impossible state - CLOSED 27 Aug 2026 09:23 UTC

`write()` treats any change to `ggd_draft_subject` / `ggd_draft_body` /
`ggd_draft_version` as a draft edit and unconditionally forces
`ggd_draft_status = "ready"` (crm_lead.py, the `if draft_changed:` branch).
Writing all three to `False` therefore produces `ggd_draft_status = "ready"`
with `ggd_draft_version = False` - a state no legitimate path should be able
to create, and one that would make a lead look draft-ready with nothing to
approve. Observed directly: `scripts/diagnose-defect13-wire.sh` cleared lead
686's draft and the record reported `draft_status = ready` immediately after.

Not blocking - nothing in the six workflows clears a draft today; only test
scripts do. `scripts/make-workflow2-retest-lead.sh` works around it with two
deliberate writes (clear the fields, then set the status on its own, which
is not a draft change and therefore sticks).

**Fixed 27 August 2026, addon bumped 19.0.1.7.0 -> 19.0.1.8.0. Verified:
`./scripts/run-addon-tests.sh` reported 108 post-tests, 0 failed, 0 errors at
09:23:33 UTC, and `docker compose restart odoo` was run immediately after so
the live worker carries the fix (see the operational note above).**

New classifier `CrmLead._ggd_is_clearing_draft(values)` sits beside the
existing `_ggd_is_suppressing`. It returns True only when the write sets
BOTH `ggd_draft_subject` and `ggd_draft_body` and both are empty after
stripping. Deliberately narrow: anything less is an edit. Requiring both
fields keeps the answer dependent only on the values being written and never
on what an individual record currently holds, so it stays correct for a
multi-record write.

`write()`'s `draft_changed` branch now splits. Both halves apply the same
revocation block, because a draft change invalidates the human's approval
whether the draft was edited or removed. The clear half then sets
`ggd_draft_version = False` and `ggd_draft_status = "empty"`; the edit half
keeps the previous behaviour (generate a version if none was supplied,
status "ready"). The shared revocation dict is now defined once instead of
being repeated, so the two halves cannot drift apart.

No production path is affected: `ggd_prepare_draft` is the only method that
writes draft subject and body, and it always writes content. Nothing else in
the addon clears both fields. The create() draft check at the
`values.get("ggd_outreach_approved")` branch is unreachable from a clear,
which never sets approval true.

Five regression tests added (103 -> 108):

- `test_clearing_a_draft_returns_the_lead_to_empty`
- `test_clearing_a_draft_still_revokes_approval`
- `test_whitespace_only_draft_values_count_as_a_clear`
- `test_emptying_only_the_subject_is_an_edit_not_a_clear` (guards against
  over-reach: a partial write must stay an edit)
- `test_clearing_a_draft_on_two_leads_at_once_clears_both`

`scripts/make-workflow2-retest-lead.sh` keeps its two-write workaround. It is
now redundant rather than required, and harmless either way; leaving it means
the script still works against an un-upgraded worker.

## Gate 3 payload correction, 27 August 2026

`scripts/gate3-workflow4-test-payloads.md` scenario 5 (unsubscribe on FX2)
carried `2026-08-26T10:00:00Z` in both its Odoo-method and raw-email shapes.
Gate 3 step 4 scenario 1 has since stored a reply on FX2 dated
`2026-08-26 17:15:00`, and `ggd_record_reply` discards any reply older than
the one already stored. Run as written, the unsubscribe test would have been
silently dropped as out-of-order and read as a pass. Both timestamps are now
`2026-08-27T12:00:00Z`.

## Gate 3 step 4 / step 6 evidence log (Workflow 4, raw-email payloads)

Baseline before scenario 2, from `./scripts/show-gate3-fixture-state.sh` at
09:28:06 UTC 27 Aug 2026: FX5 no reply, FX6A/FX6B untouched, FX2
do_not_contact=no, exactly 1 unmatched-inbound review record (id=566).

**Scenario 2 - matched by Message-ID - PASS (27 Aug 2026 ~09:30 UTC).**
FX5 (id=434) went from no reply to `category=meeting`,
`received=2026-08-26 09:05:00`. That timestamp is exactly the payload's
`date`, which is the available evidence that the reply was applied to the
record the Message-ID pointed at rather than to a sender-match guess.
AI confidence moved 0.75 -> 0.9, chatter 5 -> 7, every review flag stayed
false (correct: confidence >= 0.70). No other fixture changed and the
unmatched-inbound count stayed at 1, so nothing was written collaterally.

**Scenario 3 - unmatched inbound, first run - PASS (27 Aug 2026 ~09:32 UTC).**
Unmatched-inbound review records went 1 -> 2. New record id=810, "Manual
inbound review: Re: something we nev...", review=YES. No fixture (FX1-FX7)
changed, so the unmatched path wrote nothing to a real opportunity. Payload
date moved from 2026-08-26T09:10:00Z to 2026-08-27T09:10:00Z to keep test
data ahead of the fixture timeline. Dedup re-run pending.

**Scenario 3 - unmatched inbound, dedup re-run - PASS (27 Aug 2026 ~09:37 UTC).**
Identical payload replayed unchanged. Unmatched-inbound count stayed at 2
(id=566, id=810); no third record was created. This is the guard that keeps a
repeatedly-polled unmatched email from flooding the manual review queue.

**Scenario 4 - ambiguous sender match - PASS (27 Aug 2026 ~09:39 UTC).**
FX6A (id=435) and FX6B (id=436) share one email address on purpose, so the
sender lookup returns two candidates. Neither record received a reply:
category, received and summary all stayed empty and chatter stayed at 1 on
both. The inbound was routed to manual review instead - unmatched count 2 -> 3,
new record id=811 "Manual inbound review: Re: fixture ambiguou...", review=YES.

This is the highest-value check in step 4. A workflow that guessed here would
write a real customer's reply onto the wrong company's opportunity, and the
error would only surface when somebody acted on it. Confirmed it declines to
choose.

**Scenario 5 - unsubscribe - PASS (27 Aug 2026 ~09:43 UTC).**
FX2 (id=431): do_not_contact no -> YES, reply category meeting -> unsubscribe,
received=2026-08-27 12:00:00, summary "Sender explicitly requested to be
remov...", chatter 5 -> 7, confidence 0.9 -> 0.98, review flags all false.

The stored `received` equals the CORRECTED payload timestamp exactly. At the
payload's original 2026-08-26T10:00:00Z this reply would have been older than
FX2's stored 2026-08-26 17:15:00 and silently discarded by the out-of-order
guard - the run would have gone green with nothing suppressed. The correction
was load-bearing, not cosmetic.

UWG s7 path confirmed: once the recipient asks to be removed, the record is
marked Do not contact and no longer contactable by any downstream workflow.

**Scenario 6 - hard bounce - PASS (27 Aug 2026 ~09:45 UTC).**
FX5 (id=434): delivery accepted -> bounced, do_not_contact no -> YES,
REVIEW any=YES deliv=YES with the bounce subject stored as the review reason,
chatter 7 -> 9. Send key, confirmed_at and outbound Message-ID unchanged, so
the audit trail of the original send survived the bounce.

The quiet evidence is the unmatched-inbound count: it stayed at 3. This
payload carries NO inReplyTo header, so the only route to FX5 was the
sanitize node extracting `Original-Message-ID:` from the DSN body text. Had
that failed, the bounce would have fallen through to manual review and the
count would have gone to 4. It also had to classify mailer-daemon +
"Undeliverable" as a bounce and, with no soft-bounce wording present, as a
HARD one - only a hard bounce sets Do not contact.

Negative case (bounce whose Message-ID matches no confirmed send must be
refused) is already covered by smoke test check C2; not re-run here.

## Gate 3 steps 4 and 6: COMPLETE

Scenarios 1-6 all pass. Step 4 (reply matching: sender, Message-ID,
unmatched, ambiguous) and step 6 (unsubscribe, hard bounce) are done, with
one payload defect found and fixed along the way (scenario 5 timestamp).

Remaining in Gate 3: step 8 (error-handler proof via a genuinely scheduled
run - must be LAST) and step 9 (re-export the six workflows, confirm the
graphs match the tracked files, re-run validation). Step 9 requires clearing
n8n's pinned test data first, or the export will differ from the tracked JSON.

================================================================================
SESSION CLOSE - 27 August 2026
================================================================================

State at stop: Odoo lane GREEN. Addon 19.0.1.8.0, 108/108 tests, live worker
restarted and running that code. Nothing in this lane is half-finished and
nothing is waiting on a decision.

Closed today: defect 13 (Workflow 2 could never store a draft), the draft-clear
invariant hole, and a Gate 3 payload that would have passed without testing
anything. Gate 3 steps 4 and 6 are complete - all six Workflow 4 scenarios pass.

Files changed in this lane today:
  odoo/addons/ggd_crm/models/crm_lead.py     dict return + _ggd_is_clearing_draft
  odoo/addons/ggd_crm/tests/test_crm_lead.py 103 -> 108 tests
  odoo/addons/ggd_crm/__manifest__.py        19.0.1.6.0 -> 19.0.1.8.0
  scripts/diagnose-defect13-wire.sh          NEW - live-worker wire capture
  scripts/make-workflow2-retest-lead.sh      added RESET path
  scripts/gate3-workflow4-test-payloads.md   scenario 5 timestamp corrected
  NEXT-ACTIONS.txt                           rewritten for 27 Aug state
                                             (26 Aug copy: /tmp/NEXT-ACTIONS.26aug.bak,
                                             which does NOT survive a reboot -
                                             the git history is the real record)

Nothing was committed and no branch was changed, per the standing constraint.
The working tree still carries all of the earlier uncommitted work untouched.

Resume point is written at the top of NEXT-ACTIONS.txt under "RESUME HERE".
Short version: unpin the Workflow 4 test data and do step 9, then step 8 last
via a scheduled run, then archive lead 685.

================================================================================
GATE 3 STEP 9 - live-vs-tracked workflow comparison (27 August)
================================================================================

**A tool was missing.** `tests/workflows/test-workflow-exports.js` checks the
TRACKED files against their contract; it never looks at n8n. So "confirm the
graphs match the tracked files" had nothing behind it. Editing a workflow in
the n8n UI and forgetting to re-export would go unnoticed indefinitely.

Added `tests/workflows/compare-live-exports.js`. It compares each live export
to its committed file: node set, type, typeVersion, disabled flag, full
parameters (path by path), credential slots by name, and the connection map.

**Result on the 27 August export: 0 GRAPH, 0 UNEXPLAINED.** Every one of the
27 raw differences is accounted for:

  17  CRED   credential slot NAME only. Live kept n8n's defaults ("Header Auth
             account", "SMTP account", "IMAP account") instead of the
             documented names ("Odoo JSON-2 bearer token", "Zoho SMTP",
             "Zoho IMAP"). The bindings demonstrably work. Cosmetic, but it
             means the docs and the running system disagree on naming.
   8  DEFAULT-OMIT  n8n omits parameters equal to the node default on export
             (hoursInterval 1, schemaType fromJson, autoFix false, mailbox
             INBOX). Reported honestly as explained-but-not-proven: an absent
             key could ALSO mean someone cleared the setting, and this tool
             cannot tell the difference offline.
   1  WHITESPACE  a jsCode block differing only by a trailing newline
             (2565 vs 2566 chars, identical once normalised).
   2  CONFIRM  placeholder fields bound to live values - see below.
   1  PIN     GGD-04 still had the scenario-6 payload pinned. Not yet cleared.

**A hole in this tool, found by testing it and worth remembering.** The first
version classified any REPLACE_WITH_* -> live-value difference as "expected"
and moved on. A negative test that rewrote the Gate 4 recipient allowlist to
`attacker@example.invalid` PASSED CLEAN. A placeholder field can be bound to
anything, and these two fields decide who receives email. Placeholder-bound
values are now class CONFIRM: the bound value is printed and blocks the run
until a human reads it. Do not weaken this back to a silent pass.

Currently bound, read and confirmed correct on 27 August:
  Gate 4 recipient allowlist -> kaan@germanygrowthdesk.com
  SMTP fromEmail             -> kaan@germanygrowthdesk.com

The tool was verified in both directions before being trusted: identical
inputs report a clean match, and injected faults (added node, changed
parameter, leftover pinData, rewritten allowlist) are all caught with a
non-zero exit.

## GATE 3 STEP 9 - PASSED, 27 August 2026

Final run after unpinning GGD-04:

  GRAPH        0   no node added, removed, retyped or rewired
  UNEXPLAINED  0   no node would behave differently from its committed file
  PIN          0   editor fixtures cleared
  CONFIRMED-OK 2   both placeholder-bound values unchanged since read
  exit code    0

  ./scripts/validate-project.sh: 26/26 workflow tests, 19/19 matcher
  regressions, .env confirmed ignored, Compose config valid. PASSED.

The six live workflows in n8n match the six tracked files in behaviour.

**Confirmed bindings, and why they are hashed.** The CONFIRM class blocked on
every run, and a check that can never go green is one people learn to ignore.
The real risk was never "a placeholder is bound" - it is "the bound value
changed and nobody noticed". `tests/workflows/confirmed-bindings.json` now
stores SHA-256 of each value a human has read. A match reports CONFIRMED-OK
and passes; any change reports "VALUE CHANGED since it was last confirmed",
prints the new value and fails. Hashes, not plaintext, so the check survives
being pushed to a git remote without publishing Kaan's addresses.

Verified: recorded -> PASS exit 0; allowlist rewritten to
attacker@example.invalid -> "VALUE CHANGED", value printed, exit 1.

Re-record ONLY when a value legitimately changes, and read it again when you
do:
    node tests/workflows/compare-live-exports.js <dir> --record-confirmed

**Still open, cosmetic:** 17 credential slot NAME mismatches. Live kept n8n's
defaults ("Header Auth account", "SMTP account", "IMAP account") rather than
the documented names ("Odoo JSON-2 bearer token", "Zoho SMTP", "Zoho IMAP").
Bindings work; docs and reality disagree on naming. Renaming the three
credentials in the n8n UI clears all 17 permanently.

GATE 3 NOW HAS ONE STEP LEFT: step 8, the error-handler proof, which needs a
genuinely scheduled run and must be done last.
