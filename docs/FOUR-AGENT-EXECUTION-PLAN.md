# Four-Agent Execution Plan

Status date: 27 August 2026

## Product outcome

The immediate goal is a **working local GGD sales system for controlled use**:

- Odoo and n8n run locally and keep their data after restart;
- addon version `19.0.1.8.0` is installed and all 108 addon tests pass;
- the six tracked n8n workflows import successfully and remain inactive while
  they are tested;
- Workflows 1, 2, 4, and 5 pass fictional-data acceptance tests;
- Workflow 3 sends the exact approved draft once to a Kaan-owned test address,
  but only after Kaan explicitly approves that test;
- reply, unsubscribe, bounce, uncertain-send, and duplicate-prevention paths
  leave the correct audit record in Odoo;
- a backup and isolated restore are proven without deleting the live volumes.

This is the finish line for the local functional product. Real-prospect use is
a later go-live decision and still requires lawful-contact review. Public/VPS
deployment is deliberately outside this finish line.

## Current verified baseline

Updated 27 August 2026.

- Static project validation passes.
- Current workflow export/decision tests: 26 passed, 0 failed.
- Legacy reply-matching regression tests: 19 passed, 0 failed.
- Odoo addon `19.0.1.8.0` is installed and all 108 live tests pass.
- All six workflow exports are imported into n8n 2.34.6 and remain inactive.
- Live node type/version, stored node-set, stored connections, and shared error
  workflow checks pass for all six imports.
- Credential binding is COMPLETE. Every workflow node authenticates; only the
  credential slot NAMES differ from the documented ones (17 cosmetic
  mismatches, see Gate 3 below).
- Gate 3 execution is complete, including step 8 (closed 1 Sep): Workflows 2, 4, and 5 have run
  live against `.invalid` fixtures, and step 9 proves the live graphs match the
  tracked files.
- No email has been sent by the current workflow set. GGD-03 stays off until
  Gate 4.
- Work is committed on branch `gate3-odoo-19.0.1.8.0` and pushed. Do not reset,
  clean, stash, overwrite, or switch branches.

## One shared-workspace rule

All four participants work in this same repository. Only the main orchestrator
commits integration checkpoints. Other agents must not run `git reset`,
`git clean`, `git stash`, `git checkout`, `git switch`, `git pull`, or commit.

Each agent owns different files. If a fix requires another agent's files,
describe it in the handoff instead of editing those files.

| Participant | Owns | Must not edit |
| --- | --- | --- |
| Codex (main orchestrator) | Integration, live n8n import/execution, validation, status documents, final acceptance | Agent-owned implementation files while that agent is working |
| Claude Code | `odoo/addons/ggd_crm/**`, and `scripts/run-addon-tests.sh` only if necessary | `workflows/**`, `tests/workflows/**`, shared status documents |
| Kaan | Docker Desktop, local UI setup, credentials, human review/approval, test-mail confirmation | Source code unless the orchestrator asks for a specific edit |
| Fable 5 review session inside Claude Code for VS Code | Offline review of `workflows/**` and `tests/workflows/**` | Live n8n, Odoo addon, shared status documents, Docker volumes |

Claude Code reports only in `docs/handoffs/CLAUDE-CODE.md`. Fable 5 reports
only in `docs/handoffs/FABLE-5.md`. Codex owns this plan and the project status
documents.

## Fast execution sequence

### Gate 0 — Start safely

Work begins in parallel:

1. Kaan starts Docker Desktop. He does not expose ports, activate workflows,
   change credentials, or send mail yet.
2. Claude Code performs an Odoo-only read/review and waits for Docker if it is
   unavailable.
3. Fable 5 performs an offline workflow/test audit. Its assignment does not
   require access to Docker, the n8n UI, the n8n API, or credentials.
4. Codex protects the existing working tree, integrates handoffs, and runs the
   repository validation.

Gate passes when Docker is running and Codex confirms the four local
containers without reading or printing `.env`.

STATUS: PASSED.

### Gate 1 — Odoo green

Owner: Claude Code. Reviewer: Codex.

1. Confirm Odoo and its database are healthy without deleting or recreating
   data.
2. Upgrade `ggd_crm` to `19.0.1.8.0`.
3. Run `./scripts/run-addon-tests.sh` and require 108/108 passing.
4. Fix only confirmed addon/test defects, using the smallest safe change.
5. Record the exact result in the Claude handoff.

Gate passes only when the installed addon version is confirmed and all 108
tests pass. Workflow live execution waits for this gate.

STATUS: PASSED. Addon `19.0.1.8.0` installed, 108/108 tests passing, live Odoo
worker restarted so the running code matches the tested code.

### Gate 2 — n8n imports green

Owner/executor: Codex. Offline reviewer: Fable 5. Human credential binding:
Kaan.

1. Import/reconcile Workflows 00–05 in the order in `workflows/README.md`.
2. Keep all workflows inactive.
3. Kaan selects the already-saved Odoo, Anthropic, Zoho IMAP, and Zoho SMTP
   credentials in the n8n UI. No credential value may appear in files, logs,
   screenshots, or chat.
4. Assign Workflow 00 as the error workflow for Workflows 01–05.
5. Confirm the saved workflow graphs match the tracked inactive exports.
6. Codex records import IDs, compatibility defects, and test evidence without
   secret values in the project status. Fable reviews any required export fix
   offline and records that review in the Fable handoff.

Gate passes when all six workflows load without broken nodes and remain
inactive.

STATUS: PASSED. All six imported into n8n 2.34.6, all inactive, all
credentials bound and authenticating, GGD-00 assigned AND published as the
error workflow for 01-05.

### Gate 3 — Non-send functional flow green

Owners: Codex for live workflow execution and acceptance, Fable 5 for offline
workflow review, and Claude Code for Odoo defects. Kaan performs human review
in Odoo.

Use fictional `.invalid` records only:

1. Workflow 1 qualifies a lead and never approves outreach.
2. Workflow 2 stores one versioned draft and stops for human review.
3. Kaan reviews the exact draft; no email is sent.
4. Workflow 4 handles matched, unmatched, ambiguous, unsubscribe, and bounce
   fixtures without sending a response.
5. Workflow 5 creates one deduplicated manual follow-up activity and does not
   send mail.
6. The shared error workflow creates a sanitized review record for a
   deliberate non-SMTP failure.

Gate passes when Odoo contains the expected durable records and no workflow
has sent email.

STATUS: ALL 9 STEPS DONE. Step 8 closed 1 September 2026 (see NEXT-ACTIONS.txt
for the full evidence trail); everything else passed 27 August 2026.

| Step | What it proves | Result |
| --- | --- | --- |
| 1 | W1 qualifies without approving outreach | PASS |
| 2 | W2 stores one versioned draft and stops | PASS |
| 3 | Kaan reviews the exact draft, no email sent | PASS |
| 4 | W4 matched / unmatched / ambiguous / unsubscribe / bounce | PASS - all six scenarios |
| 5 | W5 creates one deduplicated follow-up activity | PASS |
| 6 | Bounce and unsubscribe suppression recorded in Odoo | PASS |
| 8 | Shared error handler catches a real failure | NOT DONE - see below |
| 9 | Live n8n graphs match the tracked exports | PASS - exit 0 |

Step 8 must be done LAST and cannot use the n8n CLI. Every `n8n execute` run
ends with `Cannot read properties of undefined (reading 'run')` when n8n hands
off to the error workflow; that is a CLI-mode limitation, not a defect in
GGD-00. Proving it requires a temporary SCHEDULED activation of GGD-01 so a
real scheduled failure reaches GGD-00, then switching GGD-01 off immediately
afterwards. Kaan has approved this.

Step 9 is enforced by `tests/workflows/compare-live-exports.js`, which compares
each live export to its committed file (node set, type, typeVersion, disabled
flag, full parameters, credential slot names, connection map). Placeholder
fields bound to live values are class CONFIRM: the bound value is printed and
blocks the run until a human reads it, and confirmed values are stored as
SHA-256 in `tests/workflows/confirmed-bindings.json` so a later change fails
loudly. Do not weaken CONFIRM back to a silent pass - an early version did, and
a negative test that rewrote the Gate 4 allowlist to an attacker address passed
clean.

Open and cosmetic: 17 credential slot NAME mismatches. Live n8n kept its
defaults ("Header Auth account", "SMTP account", "IMAP account") instead of the
documented names ("Odoo JSON-2 bearer token", "Zoho SMTP", "Zoho IMAP"). The
bindings work; renaming the three credentials in the n8n UI clears all 17.

### Gate 4 — One controlled send green

Owner of authorization and recipient: Kaan. Executor/reviewer: Codex. Fable 5
fixes Workflow 3 defects; Claude Code fixes Odoo defects.

1. Codex asks Kaan separately for explicit approval immediately before the
   test.
2. The recipient must be an address owned by Kaan.
3. Kaan approves the exact reviewed draft version in Odoo.
4. Run Workflow 3 once.
5. Confirm one received message, Message-ID audit, exact subject/body version,
   approval consumption, deterministic claim, and duplicate blocking.
6. Test uncertain-send recovery without automatically retrying an unresolved
   claim.

Gate passes only with Kaan's confirmation and matching Odoo/Zoho evidence.

### Gate 5 — Recovery and final acceptance

Owner: Codex. Human confirmation: Kaan.

1. Run `./scripts/validate-project.sh`.
2. Re-run the 108 addon tests and relevant workflow acceptance tests.
3. Create a backup using the existing script.
4. Restore into an isolated test project/volume set; never delete the live
   named volumes.
5. Confirm restored Odoo data and that restored n8n credentials remain
   readable without displaying their values.
6. Update `README.md`, `PLAN.md`, `NEXT-ACTIONS.txt`, and
   `docs/PROJECT-STATUS.md` to the proven state.
7. Create the final integration commit only after all validation is green.

## Copy-paste assignment for Claude Code

```text
Read AGENTS.md, PLAN.md, README.md, docs/ODOO-SETUP.md,
docs/PROJECT-STATUS.md, and docs/FOUR-AGENT-EXECUTION-PLAN.md first.

You are Agent 2, the Odoo owner. Work only in odoo/addons/ggd_crm/** and, only
if necessary, scripts/run-addon-tests.sh. Do not edit workflows, workflow
tests, or shared status documents. Do not commit or change branches. Preserve
all existing uncommitted work. Never read or print .env or secrets. Never use
destructive Docker commands.

Goal: prove addon 19.0.1.8.0 on the running local Odoo and get all 108 addon
tests passing. First perform read-only inspection. If Docker is unavailable,
write BLOCKED: DOCKER_OFF in docs/handoffs/CLAUDE-CODE.md and stop live work.
If it is available, upgrade the addon, run ./scripts/run-addon-tests.sh, fix
only confirmed Odoo/addon defects, rerun the tests, and write the commands,
results, changed files, and any blocker to docs/handoffs/CLAUDE-CODE.md. Do not
send email or activate n8n workflows.
```

## Copy-paste assignment for Fable 5 in VS Code

```text
Read AGENTS.md, PLAN.md, README.md, docs/N8N-AUTOMATION-SPEC.md,
workflows/README.md, docs/PROJECT-STATUS.md, and
docs/FOUR-AGENT-EXECUTION-PLAN.md first.

You are Agent 4, the offline n8n workflow reviewer. Review only workflows/**
and tests/workflows/**. The only file you may edit is
docs/handoffs/FABLE-5.md. Do not edit workflow JSON yet; report proposed fixes
to Codex in the handoff. Do not edit the Odoo addon or shared status
documents. Do not commit or change branches. Preserve all existing
uncommitted work. Never read, print, export, or store credential values. Never
open or modify live n8n, never run Docker commands, never activate a workflow,
and never send email.

Run ./scripts/validate-project.sh and independently inspect the six tracked
exports for broken connections, unsafe outbound paths, missing approval or
suppression gates, credential values, version mismatches with n8n 2.34.6, and
gaps in tests/workflows/test-workflow-exports.js. Record PASS/FAIL, evidence,
and exact proposed changes in docs/handoffs/FABLE-5.md, then stop. Codex will
perform all live n8n imports and executions after reviewing your handoff.
```

## Exact prompt for this Codex task

Codex is already operating in this task, so Kaan does not need to paste a new
prompt here. If this task must be reopened in a new Codex conversation, paste:

```text
Act as the main orchestrator for the GGD sales system. Read AGENTS.md, PLAN.md,
README.md, docs/PROJECT-STATUS.md, and
docs/FOUR-AGENT-EXECUTION-PLAN.md. Preserve all existing uncommitted work.
Review docs/handoffs/CLAUDE-CODE.md and docs/handoffs/FABLE-5.md, verify their
evidence, and coordinate the execution gates. You own live n8n import and
testing, repository integration, and final validation. Do not read or print
.env or credentials, do not activate a send-capable workflow, and do not send
email without Kaan's separate explicit approval for a Kaan-owned recipient.
Focus on reaching the local functional-product finish line, not adding new
scope. Start by reporting the current gate and the single next action.
```

## Kaan's immediate lane

Updated 27 August 2026. The original start-up lane is complete. Codex is out of
tokens and Fable 5 has stopped, so Kaan is directing the remaining work
directly and the single-orchestrator rule above is relaxed to that extent.

1. DONE 1 September: Gate 3 step 8. GGD-01 was temporarily activated on a
   speeded-up real schedule, a genuine scheduled failure reached GGD-00, the
   sanitized error record was confirmed in Odoo and n8n, and GGD-01 was
   switched back off (confirmed via the Executions list) with its schedule
   reverted to Hours/1. Full evidence in NEXT-ACTIONS.txt.
2. Optional tidy-up: rename the three n8n credentials to the documented names
   to clear the 17 cosmetic mismatches permanently.
3. Before Gate 5: free disk space (was at 98%) and account for the ~31 Odoo
   modules installed on 27 August, which the restore drill has to reproduce.
4. Gate 4 only after Gate 3 closes, and only with a fresh explicit approval
   given immediately before the send.

The current single next action is always kept at the top of
[NEXT-ACTIONS.txt](../NEXT-ACTIONS.txt) under "RESUME HERE".
