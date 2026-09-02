# GGD Sales System — Go-Live Plan (first real send)

Written 1 September 2026. Expands the "GOING LIVE — THE ORDERED PATH" section
of NEXT-ACTIONS.txt into an executable plan with go/no-go checks.
Scope: from today's state through the first email to a real company.

**Rewritten 2 September**, after reading germanygrowthdesk.com. The phase-1 list
this plan originally named — `bd-relationships.csv`, and the 30-company
panel-fence list behind it — was aimed at the wrong side of the market. Section 2
replaces it.

If this file and NEXT-ACTIONS.txt disagree about *what has been proven*,
NEXT-ACTIONS.txt is right — it is the evidence log. This file is the forward plan.

---

## 0. Where things actually stand

Verified from the repo and the live site today, not assumed:

| Thing | State |
| --- | --- |
| Addon `ggd_crm` | 19.0.1.9.0 written and statically checked. **Never run against Odoo** — 112 tests expected, unproven |
| Gates 1-5 | All passed 1 Sep, including the uncertain-send drill (Gate 4 item 6) |
| Workflows 00-05 | GGD-01, GGD-02 and GGD-05 have changed since the last export and need re-importing into n8n |
| Sender profile | **Filled 2 Sep** from germanygrowthdesk.com, identical block in GGD-02 and GGD-05. 30/30 static tests pass |
| GGD-03 (the only sender) | **Not published.** Hard-locked to one recipient by the Gate 4 allowlist |
| Real leads in Odoo | **None** — and no list for the real ICP exists yet |
| Mail authentication | SPF, DKIM and DMARC all published (section 5) |
| Git | Everything from 1-2 Sep is **uncommitted**, on top of `0a15aa9` |

Nothing in the system can send email today. Two things stand between here and a
real send: a prospect list for the actual ICP, and the allowlist.

## 1. Pre-flight — do this before touching leads (30 min)

**1.1 Disk — CHECKED 1 Sep, no longer a blocker.** 229 GB volume, 27 GB free
(89% used). The 27 Aug figure of 5.9 GB has since been cleared. A full backup
is ~40 MB, so there is ample room. Only run `docker system df` if you plan
another restore drill, which pulls images.

**1.2 An off-computer backup.** Everything — Odoo, n8n, credentials, the
evidence log — is on one laptop. The Gate 5 drill proved the backup *restores*;
it did not prove it exists anywhere else.

```bash
./scripts/backup.sh
```
Then copy `backups/<newest>/` to an external disk or encrypted cloud folder.
**Go/no-go:** a verified backup exists on a second physical device. Do not
start real outreach until this is true — the first real reply is data you
cannot recreate.

**1.3 Confirm the stack is healthy after this morning's scheduler fix.**

```bash
docker compose ps
./scripts/validate-project.sh          # expect 26/26 and 19/19
./scripts/run-addon-tests.sh           # expect 108 pass
```

---

## 2. Who the prospects actually are

**The ICP was inverted. The old phase-1 list is retired.**

germanygrowthdesk.com sells German market development *to manufacturers*:
customer visits and meetings, trade fair representation, sales development and
customer acquisition, and local market representation for a manufacturer not yet
ready to open its own German office. The prospect is an **export-ready Turkish or
international manufacturer that wants to enter or grow in Germany**.

`bd-relationships.csv`, `bd-sendable.csv`, `bd-research.csv` and
`panel-fence-leads.csv` are European wire-mesh and fencing *buyers*, carried over
from a previous export-sales role. They are prospects for a mill, not for GGD.
They stay on disk as history; **do not import any of them.** The four `inbound`
rows in `bd-sendable.csv` fail on their own terms as well — each claims "a reply
within the scope of their own enquiry", and those enquiries were for wire samples
and tonnage quotes, not for market-entry work.

### What a good GGD prospect looks like

The site states the qualifying criteria, and GGD-01 now scores against them:

- real production capacity and export experience
- an English or German catalogue or website, and basic certifications
- upcoming German meetings, fairs, or concrete market plans

Industries named on the site: construction materials, industrial components,
machinery, furniture, building hardware, packaging, textiles, hospitality
supplies.

Negative signals GGD-01 now scores *down*: a purely domestic retailer, a trader
with no production of its own, a service business with nothing to export, and the
one that is easy to miss — a manufacturer that already has a German subsidiary or
an established German distributor, and so needs nothing you sell.

### Where a list comes from

Two routes, and they enter the system differently.

**Route A — a cold list** (directories, fair exhibitor lists, sector
associations, search). Import with `--research-only`, columns per
`scripts/prospects-research-template.csv`. `contact_email` and `contact_basis`
must be empty; GGD-01 researches and scores every row, and the approval path can
never fire on them. This turns a raw list of 200 companies into a ranked
shortlist without contacting anyone. **Do this first, on a large list — it is the
cheapest step in the whole plan.**

**Route B — a sendable row.** Columns per `scripts/leads-template.csv`. The
importer accepts exactly four values in `contact_basis`: `consent`,
`existing_customer`, `inbound`, `trade_fair`. Anything else imports but can never
be approved — the addon refuses at the approval button, long before SMTP. That is
a mechanical property of the build, not a judgement call: a row without one of
those four values will sit in the CRM forever.

The natural source of `trade_fair` rows is your own service line. Trade fair
representation is on the website's own service list; a fair where you collect
cards and opt-ins produces exactly the rows this system was built to send.
`inbound` rows come from the site's contact form.

### The practical shape of phase 1

1. Build a research list of 100-300 manufacturers in the named industries. One
   company name and one substantive public URL per row — the about, production
   or export page, **not** a splash screen. GGD-01 reads only that page, so the
   URL choice is the single biggest lever on score quality.
2. Import it `--research-only --commit` and let GGD-01 score it overnight.
3. Read the top 20 by `ggd_fit_score`. That is your first honest signal on
   whether the prompt understands your market, and it costs only LLM calls.
4. Work the top of that list by phone, LinkedIn or at a fair. Promote the ones
   that produce a real basis into a sendable row.

## 3. Import (15 min)

```bash
# a cold research list - no address, no basis, can never be approved
./scripts/import-leads.py my-research-list.csv --research-only
./scripts/import-leads.py my-research-list.csv --research-only --commit

# a sendable row, once a real basis exists
./scripts/import-leads.py my-sendable.csv
./scripts/import-leads.py my-sendable.csv --commit
```

Both need Docker running — they write through the live Odoo. Dry run is the
default; nothing is created without `--commit`. Both templates ship with an
example row that the importer deliberately refuses, so an unedited template
cannot become a lead.

**Go/no-go:** every created lead sits at `qualification_state = pending`,
`outreach_approved = false`, no draft. Spot-check two records in Odoo.

## 4. Publish the non-sending loop and watch one full cycle (1 day)

**4.0 First: fill the sender profile and re-import (1 Sep change).** The three
LLM prompts were rewritten today — they were still test-era prompts. GGD-01
literally told the model it was qualifying a *"fictionalized"* opportunity, and
GGD-02 carried no sender identity, no product, no language rule and no length
or structure guidance, which is why a generic draft was the best it could do.

What changed, in `workflows/GGD-01/02/05`:

- **GGD-01** — evidence-only qualification, an explicit "score low and say so"
  path for thin or unreadable pages, and `personalization_angle` now has to
  quote one verifiable detail from the page. That field is what makes the later
  email read as researched.
- **GGD-02** — a `SENDER PROFILE` block, recipient facts passed as named fields
  instead of a raw JSON dump, language matching, 90–160 words, one cheap ask,
  plain text, and a closing opt-out line.
- **GGD-05** — shorter than the first email, must add one new thing, no
  guilt-tripping or false deadlines, same opt-out line.
- The opt-out line tells the recipient to reply "stop" — which is exactly what
  GGD-04 classifies as `unsubscribe` and turns into `do_not_contact`. The loop
  now closes.

**4.0b Three more app changes made the same session.**

- **A fit-score floor.** GGD-02 drafted for every qualified lead, so a weak
  lead cost the same review minute as a strong one. Its selection domain now
  carries `['ggd_fit_score','>=',60]`. Change the number if 60 is wrong for
  your market — a static test asserts a floor exists and is inside 0–100, so
  it cannot be silently removed, only deliberately changed.
- **The draft's language is now recorded.** GGD-02's validator computed a
  `language` and threw it away, so GGD-05 had to guess the follow-up language
  from a body summary — which is how a German first email acquires an English
  follow-up. New field `ggd_draft_language`, written by `ggd_prepare_draft`,
  read by GGD-05, shown on the form. It is deliberately **not** part of
  `GGD_DRAFT_FIELDS`: correcting a language code must not revoke a human's
  approval, and a test fails if anyone moves it inside. A junk tag is dropped
  and the draft is still stored — the defect 13 lesson, applied to metadata.
- **A review desk in Odoo.** CRM → *GGD review desk*. The daily habit in
  section 8 previously meant hand-building a filter every morning, which is
  the kind of step that gets skipped. It opens on the three things only a
  human can settle — needs-review records, unresolved send claims, drafts
  awaiting approval — with filters for the rest of the pipeline, including
  *Qualified below the draft floor* so the leads the new floor skips stay
  visible instead of vanishing.

Addon version is now **19.0.1.9.0**, and four addon tests were added (108 →
112 expected). Because this touches Python and adds a view and a field:

```bash
./scripts/run-addon-tests.sh     # upgrades ggd_crm and runs the suite: expect 112, 0 failed
docker compose restart odoo      # the operational rule - tests passing does NOT mean the live worker changed
```

Then confirm *GGD review desk* appears under CRM. I could not run either
command from this session — no Docker reachable — so treat the addon change as
**written and statically checked, not yet proven on your stack**. The workflow
and prompt changes are covered by the 30 static tests, which do pass here.

**One thing left to do before publishing** (the profile is done):

1. ~~Fill every `REPLACE_WITH_…` value in the profile block.~~ **DONE 2 Sep.**
   All twelve values were written from germanygrowthdesk.com: the one-sentence
   offer, the four services and their deliverables, the proof points, your name
   and role, and the sign-off (name, role, Berlin, address, domain). Two GGD-01
   rules were corrected at the same time, because they scored the wrong thing:
   `fit_score` was defined as evidence of need for goods we supply, and
   `recommended_buyer_roles` suggested *Einkauf / purchasing*. They now score
   export-readiness and German-market intent, and suggest owner or general
   manager, export manager, dis ticaret, sales director, marketing manager.
   The proof-point line carries a hard guard: the 13-accounts and EUR 750K
   figures may only be stated together with "in a previous role", never as
   Germany Growth Desk's own record. Drafts no longer arrive stamped
   `[PROFILE INCOMPLETE]`.
2. Re-import the three workflows into n8n (`workflows/README.md` has the
   procedure) and re-bind credentials. The live graphs and the tracked files
   have diverged until you do, so `compare-live-exports.js` will report
   differences on those three nodes — that is expected, not a fault.

Two regression tests were added (28 static tests now pass, up from 26): one
fails if any prompt regains the "fictional" wording, one fails if a drafting
prompt loses its sender profile or its opt-out instruction. Both were checked
by breaking them on purpose.

Then publish, in this order, and only these:

- **GGD-01** — hourly qualification poll
- **GGD-02** — draft + approval queue, every 30 min
- **GGD-05** — daily follow-up queue, weekdays 08:30

None of these can send. They research the source URL, score fit, write a draft
and park it for your approval.

**Watch for, over one full cycle:**

- [ ] GGD-01 fetches each source URL without tripping the public-URL guard
- [ ] Scores and rationales are sane for companies you know — this is your first
      honest read on whether the LLM prompt is any good on *your* market
- [ ] GGD-02 produces drafts that you would actually send. Read all of them.
- [ ] GGD-00 stays quiet. Any error it logs, read before continuing.
- [ ] Nothing appears in the review queue that you do not understand

**Go/no-go:** at least one draft you would send unedited. If the drafts are
weak, fix the prompt now — it is far cheaper than fixing it after 40 sends.

---

## 5. Mail authentication — the hard blocker before any send (1–2 h + DNS wait)

**CHECKED 1 Sep — all three are published.** Read live from public DNS:

| Record | Value found |
| --- | --- |
| SPF | `v=spf1 include:zohomail.eu ~all` — single record, correct Zoho EU include |
| DKIM | `zoho._domainkey` → `v=DKIM1; k=rsa; p=MIIBIjANBgkq…` (RSA key present) |
| DMARC | `v=DMARC1; p=none; rua/ruf=info@germanygrowthdesk.com; pct=100` |

This is a correctly configured starting position, and it removes what I
expected to be the longest-lead blocker.

Two things a DNS lookup cannot tell you, so confirm both:

- [ ] **DKIM is actually signing.** A published key only helps if Zoho is
      switched on and shows the domain as *verified* in Zoho Mail admin →
      Domains → DKIM. Check the toggle.
- [ ] **A real message passes.** Send yourself one through GGD-03 (still
      allowlisted to your own address), open the raw headers, and confirm
      `spf=pass`, `dkim=pass`, `dmarc=pass` on the `Authentication-Results`
      line. That is the only proof that counts.

Later, not now: tighten DMARC to `p=quarantine` after a few weeks of clean
`rua` reports. Leave it at `p=none` through the ramp.

**Go/no-go — hard stop.** No real send until the header check passes.

---

## 6. GGD-04 — a separate, reversible decision

GGD-04's trigger is IMAP against the live mailbox. Publishing it starts reading
your real mail; nothing else in the system does that. It is already proven on
all six scenarios, including unsubscribe and hard bounce.

Publish it **before** the first real send, not after — an unsubscribe or a
bounce that arrives with no intake running is a suppression you never record.
Publish it the same day you do step 7, so there is a short window of live mail
reading before there is any live mail to read.

---

## 7. The first real send

**7.1 The allowlist is not a switch, it is a shape change.** Today
`Gate 4 recipient allowlist (temporary)` is an IF node: `email_from` **equals**
one hard-coded address. Options, in increasing risk:

- **(A) Rolling single address** — change the value to the one company you are
  sending to, send, change it back. Maximum control, unbearable past ~5 sends.
- **(B) Small allowlist** *(recommended for the first ramp)* — change the
  operator to "is in" / a comma-list check and put the day's 3–5 approved
  recipients in it. Still a hard ceiling on who can be reached.
- **(C) Remove the guard** — rely on approval + contact basis + do-not-contact.
  Correct end state; not for week one.

Whichever you pick, the value is hash-pinned, so the comparison will fail
loudly until you re-pin — that is the design working:

```bash
rm -rf shared-files/live-export && mkdir -p shared-files/live-export
docker exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5699 \
  ggd-sales-system-n8n-1 n8n export:workflow --all --separate \
  --output=/files/live-export
node tests/workflows/compare-live-exports.js shared-files/live-export
# read every printed value, confirm it is what you intended, then:
node tests/workflows/compare-live-exports.js shared-files/live-export --record-confirmed
git add tests/workflows/confirmed-bindings.json && git commit -m "Re-pin GGD-03 allowlist for first real send"
```

**7.2 Do not publish GGD-03 yet.** Its schedule is every 15 minutes with a
limit of 10 — up to 40 mails/hour from a domain that has sent almost nothing.
For the first week, leave it unpublished and fire it with **Manual test
trigger** after each approval. That makes you the rate limiter, which is
exactly right during warm-up.

**7.3 Send one.** Pick the single strongest row from group 1 of step 2 —
best-documented basis, real company inbox, someone who asked you for something.

1. Read the draft in Odoo. Edit it if it is not what you would write.
2. Approve it yourself in Odoo (that click is the authorization record).
3. Run GGD-03 manually once.
4. Verify, exactly as in Gate 4: `delivery_status = accepted`, a real
   `last_message_id`, `last_sent_recipient` = the intended address,
   `outreach_approved` back to `false` (approval consumed),
   `last_confirmed_send_key` == `last_send_key`.
5. Check Zoho Sent. Check the headers on a copy to yourself.

**Go/no-go before the second send:** first send delivered (not bounced, not
spam-foldered where you can check), Odoo evidence complete, GGD-04 running.

**7.4 Ramp.** Day 1: 1. Day 2: 2–3. Then roughly double every few days,
holding at 10–15/day for the first two weeks. Watch the bounce rate — two hard
bounces in a small batch means the list is stale and you stop and re-verify
addresses.

---

## 8. The daily habit that makes the safety features real

The system is deliberately built to stop and ask rather than guess. That only
works if someone looks. Every working day:

- [ ] Odoo filter: `automation_needs_review` OR `delivery_needs_review` OR
      `reply_needs_review` — resolve each one
- [ ] The approval queue: read each draft, approve or edit
- [ ] n8n Executions: any red run since yesterday
- [ ] Weekly: `./scripts/backup.sh` + copy off the laptop

---

## 9. Kill switches

Know these before you need them:

| Situation | Action |
| --- | --- |
| Stop all sending, now | Unpublish GGD-03 — and confirm by the Executions list, not the toggle (`docs/GUARD-LIVE-PROOF.md`) |
| Stop one company | Set `do_not_contact` on the lead. Overrides everything else |
| Stop everything | `docker compose stop n8n` — Odoo keeps its data, no workflow can run |
| A send whose outcome is unknown | Do **not** retry. Check Zoho Sent, compare `last_send_key` vs `last_confirmed_send_key`, resolve by hand. Proven behaviour: the system will not retry on its own |

---

## 10. Timeline

| Step | Effort | Blocked by |
| --- | --- | --- |
| 0 Prove the addon, commit, back up off-laptop | 30 min | Docker running |
| 1 Build the research list (100-300 manufacturers) | **2-4 h of your work** | — |
| 2 Import `--research-only` and let GGD-01 score it | 15 min + overnight | Steps 0, 1 |
| 3 Read the top 20 scores, judge the prompt | 1 h | Step 2 |
| 4 Watch one non-sending cycle | 1 day elapsed, ~1 h attention | Step 2 |
| 5 SPF/DKIM/DMARC — published; confirm DKIM + a real header check | 15 min | — |
| 6 Publish GGD-04 | 15 min | Step 5 |
| 7 Promote a scored lead to a sendable row, then send one | 1 h | Steps 3, 5, 6 |

**The critical path is step 1, and it is list-building, not technology.** Nothing
downstream can start without rows. Steps 0 and 5 can be done tonight in parallel;
neither can send anything.

---

## What still needs you

Everything doable from a session without Docker is done. What is left needs your
terminal, your mailbox, or your judgement.

| # | Action | Where | Time |
| --- | --- | --- | --- |
| 1 | **Build the research list** — 100-300 manufacturers, one substantive public URL each | Directories, fair exhibitor lists, LinkedIn | 2-4 h |
| 2 | `./scripts/run-addon-tests.sh` then `docker compose restart odoo` — proves 19.0.1.9.0 on your stack, expect 112 | Terminal, Docker up | 10 min |
| 3 | `git add -A && git commit` — two days of work is uncommitted | Terminal | 2 min |
| 4 | `./scripts/backup.sh`, then copy the newest `backups/` folder off the laptop | Terminal + external disk | 15 min |
| 5 | Confirm DKIM shows *verified* in Zoho Mail admin | Zoho admin panel | 5 min |
| 6 | Re-import GGD-01, GGD-02, GGD-05 into n8n, re-bind credentials, publish, watch one cycle | n8n | 30 min + 1 day |

Items 2, 3 and 4 are 30 minutes together and are the ones that protect what
already exists. Item 1 is the only one nobody can do for you.

---

## Open questions for Kaan

1. **Allowlist shape** — A, B or C in step 7.1? GGD-03's Gate 4 allowlist is
   still exactly as it was, on purpose. It is the one node where a change that
   cannot be run here is a change that should not be made here: it decides who
   can receive email, its value is hash-pinned as an audit control, and every
   option supporting more than one recipient either weakens the exact match or
   moves the pinned value somewhere the comparison tool stops classifying it as
   a placeholder. Decide the shape and it is a ten-minute change with the pin
   re-recorded.
2. **Which industries first?** The site names eight. A research list built
   across all eight scores worse than one built across two, because
   `personalization_angle` gets sharper when the pages look alike enough for
   you to judge the scores.
3. **Language of first contact.** Rule 1 writes in the recipient's language, so
   Turkish manufacturers get Turkish email from a Berlin desk. That is probably
   right — but it is a choice, and `ggd_draft_language` now carries it through
   to the follow-up so the two never diverge.
