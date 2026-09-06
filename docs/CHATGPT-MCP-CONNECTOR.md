# ChatGPT desktop -> Odoo CRM connector

A local MCP connector that lets the ChatGPT desktop app read the Germany
Growth Desk CRM and, only when you ask for it, create researched leads, save
qualification assessments, save reply drafts, and make one of five guarded
changes to an existing opportunity. Tickets #59 and #65.

Nothing about it is public. Odoo, n8n and both databases stay bound to
`127.0.0.1` exactly as they are today, the connector runs on your Mac as a
child process of the desktop app, and it uses your existing ChatGPT Plus
login. There is no OpenAI API key, no paid connector, no hosting and no
tunnel.

---

## The one thing to know first

Local connectors like this one work in the **Codex side of the ChatGPT
desktop app** (and in the Codex CLI and the IDE extension, which share the
same configuration file). They do **not** work in ordinary ChatGPT
conversations on the web, because, in OpenAI's words, ChatGPT web does not
read local Codex configuration files.

So: ask for these reports in the desktop app, in a Codex thread. The tools
are registered globally, so they are available in every desktop session, not
only when you have this project open.

---

## Daily use

Ask in plain language. Some prompts that work:

**Customer**

- "Find the opportunity for Fictional Panels and show me everything on it,
  including the recent chatter."
- "Search the CRM for companies with 'Verpackung' in the name."
- "What is the current state of opportunity 42 — has it been qualified, is
  there a draft, has anyone replied?"

**Pipeline**

- "Give me a pipeline report grouped by stage."
- "Pipeline by salesperson for opportunities created since 2026-08-01."
- "How much expected revenue is sitting in stages before Qualified?"

**Follow-up**

- "What is overdue? Show me the follow-up report."
- "List the ten most overdue activities and who they are assigned to."

**Reports and today's work**

- "Show me the dashboard."
- "Show today's work queue and why each company is on it."
- "Contact coverage for Istanbul — how many have an email or a phone?"
- "Run the data quality report and list what is missing."
- "Which companies are ready to send to, and which are blocked?"
- "Qualification report: average fit score and the confidence bands."
- "Counts by industry, with the average fit score for each."

**New leads (writes to Odoo — only when you ask)**

- "Create a lead from https://www.fercelik.com/home, then save a sourced
  qualification."
- "I found this company at a trade fair — create a lead from
  https://example.com/en/about with contact Ms Y, Head of Procurement."

**Qualification (writes to Odoo — only when you ask)**

- "Save this assessment on opportunity 42: fit score 74, confidence 0.85,
  summary …, angle …, source https://…"

**Replying**

- "Show me opportunity 42's latest reply, then draft an answer and save it."
- "Save this as the reply draft on opportunity 42: …"

Saving a draft stores it on the opportunity for you to read; it never sends
it and never approves outreach. Odoo refuses the write outright if the
contact is suppressed by Do not contact or has unsubscribed, and it replaces
whatever draft Workflow 4 last suggested on that record.

**Working an opportunity (writes to Odoo — only when you ask)**

- "Add the contact details you just found to opportunity 42, with the pages
  you read them from."
- "I called them this morning — record that on opportunity 42, then move it to
  Contacted."
- "Schedule a call on opportunity 42 for next Tuesday."
- "Draft the first outreach email for opportunity 42 in German and save it."

All four go through `ggd_opportunity_action`; see *Working an opportunity*
below for what each one requires and what it refuses.

The desktop app asks before running any of the writes, provided your
tool-approval setting is not `auto`. Check it under **Settings** in the desktop
app; the `writes` mode prompts for anything not marked read-only, and this
connector marks six tools read-only and four — `ggd_create_lead`,
`ggd_save_qualification`, `ggd_save_response_draft` and
`ggd_opportunity_action` — as writes.

### Reading the answers honestly

Every list answer carries `total_matching`, `returned` and `has_more`. If
`has_more` is true you are looking at one page, not the whole picture; the
answer says which offset to ask for next. The pipeline report carries
`complete`, and if it is false it says how many opportunities it could not add
up. Ask for the numbers if the summary reads too confidently.

`ggd_report` answers in the same spirit. Every report carries `as_of`,
`timezone`, `complete`, `scanned`, `total_matching` and `warnings`, and
`warnings` is present even when it is empty so that a silent answer is never
mistaken for a clean one. Two habits are worth keeping:

- **`complete: false` means the numbers are partial.** The report reads at
  most 500 records in one pass and adds them up here rather than asking Odoo
  to group, so past that it says how many it saw out of how many matched, and
  the first warning tells you to narrow it with `date_from`, `date_to` or a
  filter. It never rounds a partial scan up into a total.
- **`unavailable` is not zero.** A metric the CRM cannot yet source comes back
  under `unavailable` with the reason, never as `0`. See *What the reports
  will not claim* below.

### Why the answers look terse

Everything the connector returns sits in the conversation's context and is
charged again on every later turn, so it is deliberately compact:

- **Empty fields are omitted.** A company with no published phone number has
  no `phone` key, rather than `"phone": null`. `false` and `0` are kept, since
  "not approved" and "fit score 0" are answers rather than absences.
- **Pages are small by default** — 10 records, 5 chatter messages. Every
  answer reports `total_matching` and the offset for the next page, and you
  can ask for up to 50 at a time ("show me 40 of them").

Together with a leaner tool declaration this cut what a typical reporting
session puts in context by roughly a third. If you would rather see more per
answer, `DEFAULT_LIMIT` and `DEFAULT_HISTORY` at the top of
`mcp/ggd_odoo_mcp.py` are one line each.

---

## The ten tools

| Tool | Reads or writes | What it is for |
| --- | --- | --- |
| `ggd_connection_status` | read | Is Odoo up and does the key still work. Run it first when anything fails. |
| `ggd_search_records` | read | Find opportunities, leads, companies or contacts. Returns ids. |
| `ggd_get_opportunity` | read | One opportunity, whole or by section, with activities and chatter. |
| `ggd_report` | read | Twelve named reports over the pipeline. |
| `ggd_pipeline_report` | read | Counts and expected revenue by stage, salesperson or qualification state. |
| `ggd_followup_report` | read | Overdue Odoo activities, most overdue first. |
| `ggd_create_lead` | **write** | Opens one new Target Identified opportunity from a company you researched. Refuses duplicates. |
| `ggd_save_qualification` | **write** | Saves a fit assessment through the addon's own audited method. |
| `ggd_save_response_draft` | **write** | Saves one reply draft onto an opportunity for you to read in Odoo. It does not send it. |
| `ggd_opportunity_action` | **write** | One of five guarded changes to an existing opportunity: contact enrichment, a recorded manual contact, a stage move, a follow-up activity, an outreach draft. |

### The reports

`ggd_report` takes a `report_type` and nothing else is required. It also
accepts a `date_from`/`date_to` window on the creation date, an `as_of` date,
a `group_by` for the two grouped reports, `detail_level`, `limit`/`offset`,
and a fixed `filters` object holding only `salesperson`, `stage`, `country`,
`city`, `industry`, `qualification_state`, `min_fit_score`, `max_fit_score`
and `do_not_contact`. Any other key is refused by name before a request is
sent — there is no Odoo domain, field list, model or method here.

| `report_type` | What it counts |
| --- | --- |
| `dashboard` | One snapshot: open pipeline and revenue by stage, qualification states, contact coverage, approvals and send-readiness, delivery and replies, review queues, overdue work. |
| `daily_action` | Today's queue. One row per opportunity with reason codes, most urgent reason first, then id. Do-not-contact records are counted, never queued. |
| `pipeline` | Counts and expected/weighted revenue grouped by `stage`, `salesperson` or `qualification_state`. |
| `qualification` | Counts by state, and average, median and banded scores over the **scored** records only. |
| `contact_coverage` | Named contact, email, phone, either, neither, and how many carry a recorded contact basis. |
| `outreach_readiness` | Qualified, contact present, draft ready, draft approved, human approved, send-ready, suppressed, review-blocked. |
| `activity` | Open Odoo activities by owner, type and due bucket, with drill-down rows. |
| `reply_delivery` | Confirmed sends, replies, reply categories, bounces, and unresolved delivery/reply review. |
| `industry_market` | Counts, expected revenue and average fit score grouped by `country`, `city` or `industry`. |
| `data_quality` | Counts by issue code, plus rows of ids and their codes. |
| `conversion_funnel` | Unavailable — see below. |
| `usage_efficiency` | Unavailable — see below. |

Reason codes in `daily_action`: `needs_human_review`, `reply_review`,
`automation_review`, `overdue_activity`, `needs_qualification`,
`needs_contact`, `needs_draft`.

Issue codes in `data_quality`: `missing_company_name`, `missing_source_url`,
`missing_website`, `missing_named_contact`, `missing_contact_method`,
`missing_owner`, `qualification_missing`, `qualification_needs_review`,
`automation_needs_review`, `invalid_email_shape`, `invalid_url_shape`,
`suppressed_but_approved`, `approved_version_mismatch`,
`incomplete_send_audit`, `overdue_activity`.

`send_ready` is a reading of the outbound gate, never a grant of it: approved
by a human, not Do-not-contact, draft status `approved` with the approved
version still matching the current one, and an email address present. A
contact basis is recorded and reported but is deliberately not one of the
conditions.

### What the reports will not claim

Four things the CRM cannot source honestly today. Each is reported as
unavailable, with the reason, rather than as a zero or an estimate:

| Missing metric | Why |
| --- | --- |
| `conversion_funnel` | Nothing records stage *changes*, only the stage a record sits in now. A snapshot of where things sit is not a conversion rate, so the whole report returns `available: false`. |
| `usage_efficiency` | No per-call telemetry is stored, and this connector cannot see ChatGPT's token usage. Payload bytes are not billed tokens and are not reported as them. |
| `contact_coverage.source_backed` | Contact provenance — source URL, retrieval time, contact kind — is not stored yet, so coverage cannot be split into source-backed and unsourced. |
| `reply_delivery.bounce_hardness` | Odoo records one `bounced` state; hard and soft bounces are not distinguished. |

Two data-quality codes are named in the same way rather than guessed:
`qualification_stale`, because no staleness horizon is agreed or stored, and
`possible_duplicate`, because deciding it needs a whole-table comparison that
a capped scan would answer with false negatives.

One more denominator worth knowing: `ggd_fit_score` is an integer, so a lead
nobody has assessed stores `0`. Every score average, median and band divides
by the **scored** count — records whose qualification state is `ready`,
`review` or `failed` — never by the scan, because averaging an unassessed
record's `0` would be an invented number. For the same reason a
`max_fit_score` filter warns that it matches unscored records too.

### Narrowing a search

`ggd_search_records` takes the same fixed vocabulary: `created_from`,
`created_to`, `updated_from`, `updated_to`, `country`, `city`, `industry`,
`qualification_state`, `min_fit_score`, `max_fit_score`, `has_email`,
`has_phone`, `has_named_contact`, `has_contact_method`, `do_not_contact`,
`outreach_approved`, `draft_status`, `delivery_status`,
`has_overdue_activity`, `needs_review`. Dates are `YYYY-MM-DD`.

The GGD filters only exist on opportunities and leads. Asking for one while
searching companies or contacts is refused by name rather than quietly
dropped, because a silently ignored filter turns a narrow question into a
wide answer that looks narrow.

`detail_level` defaults to `compact`, which is exactly what this tool has
always returned. `standard` adds the research and next-step fields; `full`
returns every field including the free text and is capped at 10 rows a page.

### Reading one opportunity by section

`ggd_get_opportunity` still returns the whole record when you pass only an
id — nothing about the existing answer changed. Pass `sections` or
`detail_level` and it returns only what you asked for, and only fetches that:
`identity`, `qualification`, `contact`, `outreach`, `delivery`, `reply`,
`activities`, `chatter`. The default is everything except `activities` and
`chatter`, both of which cost an extra round trip and are opt-in.

`detail_level` here means `compact` (no free text at all), `standard` (the
short text fields) or `full` (adds the paragraph-length `description` and
`ggd_draft_body`).

### What `ggd_create_lead` does, and stops at

It creates **one opportunity at the Target Identified stage** and nothing more
— the stage `PLAN.md` defines as "company and source are recorded". The fields
it accepts are exactly the "Required data before qualification" list in
`docs/ODOO-SETUP.md`: company name and source URL are required, and
opportunity name, website, contact name, job title, email, phone, city,
country, industry, product focus and a lead-source note are optional. It
accepts no model name, method name, field list, domain or raw Odoo payload,
and it builds the values dict itself — extra arguments naming Odoo fields are
ignored, and a payload carrying any approval, draft, send, Do-Not-Contact or
score field is refused before it is sent.

So a lead it creates is **never** approved for outreach, has no draft, no send
key and no contact basis, and the tool reports that gate state back to you
after the create so you can see it rather than take it on trust. There is no
tool here that could later change any of that.

**It refuses to create a duplicate.** Before creating, it searches open
`crm.lead` records for the company name, the website host (with `www.`
stripped, so a company's pages match each other) and the email if you gave
one. If anything matches, nothing is created and it hands you the existing
id(s) instead, telling you to qualify that record. A matching `res.partner`
contact is reported but does not block — a customer record is not a pipeline
record.

Two things it will refuse rather than accept: a `source_url` that is not
`http://` or `https://`, and any field long enough to be a pasted web page
(summarise instead — nothing is silently truncated). It also refuses text that
looks like a handed-over credential.

Archived records do not count as duplicates: a company that was dropped or
lost can legitimately be researched again.

### What a false return means

`ggd_save_qualification` calls `crm.lead.ggd_apply_qualification`, which
returns `false` when the confidence is below 0.70. **That is a successful
save**: the assessment is written, `ggd_qualification_state` becomes `review`,
and the record is routed to a human. It is not a failed write, and it must
never be retried — a retry would post a second chatter entry over a record you
are already reviewing. The connector says this in words in its answer, and
reads the record back from Odoo so you can see what was stored.

### The confidence field is shared

`ggd_ai_confidence` is written by both qualification and reply analysis. A
later reply analysis on the same opportunity overwrites the confidence a
qualification stored. That is the current schema; ticket #59 deliberately does
not redesign it or add a second scoring scheme.

### Working an opportunity

`ggd_opportunity_action` (ticket #65) is one tool with a fixed `action`, not
five tools. Five would have cost five descriptions and five schemas in the
tool list on every turn of every conversation, whether used or not, and would
still have needed the same checks behind them.

Every action needs three things: `opportunity_id`, the `action` name, and
`expected_write_date` — the `last_change` value from the record as you read
it. If the record changed in between, the write is refused whole, with the
current `last_change` in the answer so a retry needs no second read. Arguments
belonging to another action are refused by name rather than ignored.

| Action | Also needs | What it does |
| --- | --- | --- |
| `enrich_contact` | `contact`, `source_urls`, `researched_at`, `confidence` | Fills contact name, job title, email, phone or contact URL from research you can point at. |
| `record_manual_contact` | `channel`, `occurred_at`, `summary`, `idempotency_key` | Records that a person really did make contact: `email`, `call`, `linkedin`, `meeting` or `other`. |
| `transition_stage` | `target_stage`, `expected_stage` | Moves the opportunity between documented non-terminal stages. |
| `schedule_activity` | `activity_type`, `summary`, `deadline`, `idempotency_key` | Creates one Odoo To-Do or Call. |
| `save_outreach_draft` | `subject`, `body`, `language`, `idempotency_key` | Saves an initial outreach draft for you to approve later in Odoo. |

**Contact enrichment never guesses and never clears.** At least one public
source URL, a research time and a confidence are required, and they are stored
on the record next to the details themselves. An empty value is refused: this
tool cannot be used to remove a contact detail. If a *different* value is
already stored the answer is `conflict`, naming the fields and writing
nothing; replacing it needs `overwrite: true`, which is a thing to ask for
rather than a default. Changing the recipient address while outreach is
approved is refused outright (`approval_locked`) even with `overwrite`,
because Odoo would otherwise re-point the approval at an address you never
saw. Revoke the approval in Odoo first.

**Stages it can reach.** Target Identified, Qualified, Draft Prepared, Waiting
for Approval, Contacted, Meeting Proposed, Meeting Booked, Meeting Held and
Active Opportunity. Reply Received, Won, Lost and Do Not Contact cannot be
named at all: the first belongs to the reply workflow and the other three are
your decision, in Odoo.

**Contacted has to be earned.** It needs either a send Odoo itself confirmed,
or a manual contact recorded through `record_manual_contact`. A saved draft
counts for nothing — a draft is a message that has not been sent, and letting
it move a record to Contacted would make the pipeline report outreach that
never left the building.

**Activities are assigned by rule, not by request.** The opportunity's own
salesperson gets it when there is an active internal one; otherwise the
reporting user does. There is no way to schedule work in a third person's
name. Deadlines must be today or later and within a year.

**Saving a draft is not approving one.** It goes through the same
`ggd_prepare_draft` the drafting workflow uses, which consumes any older
approval — a human approved one specific version, and this is not that
version. The answer carries `draft_version`, `approved_draft_version` and
`approved_matches_draft`, and straight after a save the last of those is
`false`. Nothing here approves, queues, claims, finalises or sends.

**Retries are safe where a key is required.** `record_manual_contact`,
`schedule_activity` and `save_outreach_draft` each take an
`idempotency_key` you choose. Repeating a call with the same key returns the
first result — `already_recorded`, `already_scheduled`, `already_saved` — and
creates nothing new.

**Refusals come back as codes**, not just prose, so a repeat attempt can be
decided on rather than guessed at:

| `reason_code` | Meaning |
| --- | --- |
| `stale_record` | The record changed after you read it. Retry with the `write_date` in the answer. |
| `stale_stage` | It is no longer in the stage you read. |
| `conflict` | A different value is already stored in a contact field. |
| `approval_locked` | Outreach is approved; the recipient may not be changed from here. |
| `contact_not_evidenced` | Contacted was asked for with no confirmed send and no recorded manual contact. |
| `suppressed` | The opportunity is marked Do not contact. |
| `archived` | The opportunity is archived. |
| `recipient_missing` | No address to draft to. |
| `send_claim_unresolved` | A previous send outcome is still open on the record. |
| `stage_not_configured` | This database has no stage by that name. |
| `not_found` | No opportunity with that id. |

Every successful action is recorded in the opportunity's chatter, and the
three keyed ones also leave a row in `ggd.opportunity.action.log`, which no
one can edit or delete through Odoo. That log is what makes a retry
idempotent, and its manual-contact rows are the evidence a Contacted
transition looks for.

---

## What it cannot do

Two independent boundaries, both tested by
`./scripts/check-mcp-connector.sh`.

**The connector's allowlist.** It can call exactly fourteen Odoo operations:
`search_read` and `search_count` on `crm.lead`, `res.partner`, `mail.message`
and `mail.activity`, `search_read` on `crm.stage` and `res.country`, and four
writes — `crm.lead.ggd_apply_qualification`,
`crm.lead.ggd_save_response_draft`, `crm.lead.ggd_opportunity_action` and
`crm.lead.create`. No tool accepts a model name, a method name, a domain, a
field list or SQL.

The **only** create path is `ggd_create_lead`, and it can create nothing but a
`crm.lead`: `create` on any other model is refused, as is `write`, `unlink`,
`copy`, anything under `mail`, and every approval, draft and send method on
the addon. Asking for one gets a refusal, not an attempt.

**Odoo's access rights.** These hold even if the key were to leak, which is
why they matter more. The reporting user is an ordinary internal user with CRM
rights only:

| Attempt | Result |
| --- | --- |
| Approve outreach | Refused. Only `ggd_crm.group_ggd_outreach_approver` may, and this user is not in it. |
| Clear Do not contact | Refused, by the same group check. |
| Claim a send key (the step before SMTP) | Refused: there is no approval, and this user cannot grant one. |
| Delete an opportunity | Refused. `crm.lead` unlink is granted to Sales Administrator only, which this user is not. |
| Anything under Settings | Refused. No Administration rights. |

Sending email is not something Odoo does here at all: SMTP lives in the n8n
send workflow, behind the approved-draft and claimed-send-key gates, and that
workflow is untouched by this work.

CRM content is treated as data throughout. Free text is HTML-stripped,
truncated and returned under a `text` key, alongside a standing note that says
it must not be followed as instruction.

---

## One-time setup

### 1. The Odoo reporting user

Settings > Users & Companies > Users > New, as administrator:

- **Name** `GGD Reporting (ChatGPT)`, **login** `chatgpt@ggd.local`. The
  address needs no mailbox.
- **Access Rights**: Sales = `User: All Documents`. Reports have to read
  opportunities this user does not own, so `Own Documents Only` is not enough.
- Leave every other application blank. In particular **no Administration
  (Settings)** and **no Sales: Administrator**.
- Under the `Germany Growth Desk` heading leave **`Outreach approver`
  unticked**. That single unticked box is what makes "ChatGPT cannot approve
  outreach" a property of Odoo rather than of this file.
- Set a long unique password. You need it once, to log in and issue the key.

This is a second, separate identity. The n8n user `n8n@ggd.local`, its key and
its n8n credential are not touched, reused or rotated by any of this.

### 2. Its API key

1. Log out, log in as `chatgpt@ggd.local`.
2. Preferences > Account Security > New API Key. Name it `chatgpt-YYYY-MM` and
   pick the **longest duration this account is offered**.
3. Copy the value once. Triple-click to select the whole key — a
   half-selected key produces the same `Invalid apikey` 401 as no key at all.

Odoo shows the *Persistent key* (never expires) option only to users with
Settings rights, which this account deliberately does not have. **The key will
therefore always carry an expiry date.** Put that date in the calendar with a
reminder two weeks before. An expired key does not merely stop working: Odoo's
autovacuum then deletes it, so it disappears too. That is exactly how
Workflow 2 died on 27 August 2026.

### 3. Store it in the Keychain

In your own Terminal. The `-w` with no value makes `security` prompt for the
key, so it never reaches the command line, your shell history or any log:

```bash
security add-generic-password -U -D "GGD Odoo API key" -s "ggd-odoo-mcp" -a "chatgpt@ggd.local" -T /usr/bin/security -w
```

Paste the key at the `password data for new item:` prompt, then again to
confirm. `-T /usr/bin/security` is what lets the connector read the item later
without a Keychain dialog on every call.

No agent, script or log in this project ever sees the value. The connector
reads it from the Keychain at the moment of each call.

### 4. Register the connector with the desktop app

Already done, but this is the command, and it is also how you would restore it:

```bash
cp ~/.codex/config.toml ~/.codex/config.toml.bak-$(date +%Y%m%d)
```

```bash
"/Applications/ChatGPT.app/Contents/Resources/codex" mcp add ggd_odoo --env GGD_ODOO_URL=http://127.0.0.1:8069 --env GGD_ODOO_DB=ggd --env GGD_ODOO_LOGIN=chatgpt@ggd.local --env GGD_KEYCHAIN_SERVICE=ggd-odoo-mcp -- /usr/bin/python3 "/Users/kaan/Desktop/GGD -Sales-System /mcp/ggd_odoo_mcp.py"
```

Only non-secret settings are stored there. Restart the ChatGPT desktop app,
then check **Settings > MCP servers**: `ggd_odoo` should be listed with nine
tools.

### 5. Prove it

```bash
./scripts/check-mcp-connector.sh
```

It creates three fictional `[GGD-MCP-TEST]` opportunities on the reserved
`.invalid` domain, drives the connector over stdio the way the desktop app
does, checks every boundary in the table above, confirms the outgoing mail
queue did not move, and archives the fixtures. It never deletes anything.

---

## Key expiry, renewal and revocation

**Check what exists** — both scripts print owner, groups and expiry, never a
key value, so their output is safe to paste anywhere:

```bash
./scripts/check-odoo-api-keys.sh
```

```bash
./scripts/check-odoo-automation-user.sh
```

**Renew** — before the expiry date, and immediately if the key may have been
exposed (a shared screenshot, a pasted log, a laptop handed on):

1. Log in to Odoo as `chatgpt@ggd.local`, issue a **new** key named
   `chatgpt-YYYY-MM`.
2. Overwrite the Keychain item with the same command as step 3 above; `-U`
   updates the existing item in place.
3. Run `./scripts/check-mcp-connector.sh`.
4. Only once that passes, delete the **old** key in Preferences > Account
   Security.

Nothing else changes: the desktop configuration points at the Keychain item,
not at a key, so a rotation needs no edit to `config.toml` and no restart.

**Revoke** — to stop ChatGPT reaching the CRM at all, any one of these is
enough, in increasing order of finality:

```bash
"/Applications/ChatGPT.app/Contents/Resources/codex" mcp remove ggd_odoo
```

```bash
security delete-generic-password -s "ggd-odoo-mcp" -a "chatgpt@ggd.local"
```

…and, the one that holds regardless of what is on this Mac: delete the key in
Odoo under that user's Preferences > Account Security, or archive the
`GGD Reporting (ChatGPT)` user. Do that when the integration is retired.

Every write this connector makes is attributed to `GGD Reporting (ChatGPT)` in
the lead's chatter, so the audit trail names it.

---

## Troubleshooting

| Symptom | What it means |
| --- | --- |
| No `ggd_odoo` in Settings > MCP servers | The desktop app has not been restarted since it was registered. |
| `credentials_unavailable` | No Keychain item, or the login keychain is locked. Re-run the `security add-generic-password` command. |
| `authentication_failed`, "invalid or expired" | The key expired or was mistyped. Issue a new one and update the Keychain item. |
| `unreachable`, "Odoo is not reachable" | The stack is down. `docker compose up -d` in the project directory. |
| `access_denied` | Odoo refused it for this user. That is usually the boundary working, not a bug. |
| `not_allowed` | You asked for something outside the connector's nine permitted operations. |

---

## Files

| Path | What it is |
| --- | --- |
| `mcp/ggd_odoo_mcp.py` | The connector. Standard library only, runs on `/usr/bin/python3`, no install step. |
| `tests/mcp/test_ggd_odoo_mcp.py` | Offline tests. No Odoo, no key, no network. Run by `./scripts/validate-project.sh`. |
| `scripts/check-mcp-connector.sh` | The live end-to-end check. Needs the key in the Keychain. |
| `scripts/mcp_live_check.py` | The driver that check-mcp-connector.sh runs. |
| `odoo/addons/ggd_crm/models/crm_lead.py` | `ggd_opportunity_action` and the rules behind it. Odoo decides, not the connector. |
| `odoo/addons/ggd_crm/models/ggd_opportunity_action_log.py` | The append-only log that makes retries idempotent and evidences a manual contact. |
| `~/.codex/config.toml` | Outside this repository. Holds the `[mcp_servers.ggd_odoo]` entry and no secret. |
