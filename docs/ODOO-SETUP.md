# Odoo Setup for Germany Growth Desk

## Applications

Install only what the first workflow needs:

1. CRM
2. Contacts, if it is not already installed as a dependency
3. Germany Growth Desk CRM Controls, from the included custom addons directory

Avoid adding Marketing Automation, Studio, Sales, Accounting, or other applications until a concrete requirement exists.

## Pipeline stages

Create these CRM stages in order:

| Sequence | Stage | Exit condition |
| ---: | --- | --- |
| 10 | Target Identified | Company and source are recorded |
| 20 | Qualified | Fit score and fit assessment reviewed |
| 30 | Draft Prepared | Draft exists; nothing sent |
| 40 | Waiting for Approval | Contact basis recorded; Kaan must decide |
| 50 | Contacted | Approved email sent and logged |
| 60 | Reply Received | Reply classified and summarised |
| 70 | Meeting Proposed | Specific dates or format proposed |
| 80 | Meeting Booked | Calendar date confirmed |
| 90 | Meeting Held | Notes and buyer feedback recorded |
| 100 | Active Opportunity | Commercial next step exists |
| 110 | Won | Engagement or commercial outcome confirmed |
| 120 | Lost | Reason recorded |
| 130 | Do Not Contact | Future outreach suppressed |

Keep `Do Not Contact` as a visible stage and also select the `Do not contact` checkbox. The checkbox is the machine-enforced control used by n8n.

## Required data before qualification

- Opportunity name
- Company name
- Website/source URL
- Contact person and role, if known
- Work email, if legitimately available
- Country and industry
- Product/capability focus
- Lead source

## Required data before approval

- Fit assessment
- Personalisation angle
- Contact basis
- Contact-basis note with the supporting facts
- Draft reviewed by Kaan
- `Do not contact` is false

The approval button refuses approval when the contact basis is missing or the opportunity is marked `Do not contact`.

## Working views: country, product groups, and the selection bar

Since addon 19.0.1.23.0 the pipeline can be narrowed to the customers being
worked on - "Türkiye + Wire + Manufacturer" - and that selection can be saved,
reopened, and acted on in bulk. Nothing about the sales stages changed: the
kanban columns are still the pipeline in the table above, and the selection
filters the cards inside them.

### Where the classification lives

Four dimensions, and each one uses a single field rather than a second record
of the same fact:

| Dimension | Field | Notes |
| --- | --- | --- |
| Country | `country_id` (`Country` on the opportunity) | Where the company is. Odoo's own field, filled from the linked company. This is not a target market; there is no target-market field. |
| Product group | `ggd_product_group_ids` (`Product groups`) | The managed list below. Several per opportunity. |
| Company type | `ggd_company_type` (`Company type`) | Manufacturer, Distributor, or Wholesaler. |
| Lead source | `source_id` (`Source`) | Odoo's own UTM source: create `Trade fair`, `Referral`, `Research` and pick one. |

The free-text `Product / capability focus` paragraph is untouched by all of
this and is never rewritten from a group. It is what a researcher wrote about
the company; the group is the shelf it is filed on.

### Managing product groups

**Settings must be in developer-free normal use: CRM > Configuration >
Pipeline > Product groups.** The menu is visible to a Sales Administrator.

The addon installs four to start with - `Wire`, `Pipe`, `Fasteners`,
`Machinery` - and every edit survives an addon upgrade. A Sales Administrator
may add a group, rename one, reorder them, and archive one.

**Retire a group by archiving it. Nobody may delete one**, including the
administrator: deleting would take the links with it and quietly rewrite what
an opportunity was once classified as. An archived group

- disappears from the pickers and from the bulk action, so nothing new can be
  filed under it;
- stays visible on every opportunity that already carried it;
- leaves those opportunities findable through the **Only archived product
  groups** filter, which is the case that would otherwise hide - the record
  looks classified and appears under no live group.

### Narrowing the pipeline

Above the board (and above the list) sits the selection bar:

`Country ▾  Product group ▾  Company type ▾  More ▾ | the four state chips | N leads · Clear selection · Daily send cap`

- Several values inside one picker mean **either** (Türkiye or Poland); values
  in two pickers mean **both** (Türkiye and Wire). An opportunity in two
  product groups matches once and is counted once.
- Every control leaves an ordinary Odoo facet behind, so the same selection
  can be built or edited from the search bar, and the Filters menu shows it.
- The four state chips - Sendable today, Needs review, Unresolved claim,
  Replies - now count **inside the current selection**, so they never
  contradict the board.
- **Daily send cap** is printed apart from the chips and labelled
  *system-wide*, because it limits outbound send claims across the whole
  installation in any 24 hours. It is not a quota for the selected group.
- **Clear selection** undoes what the bar set and leaves the default
  `My Pipeline` scope alone.
- **More** holds the follow-up states and the classification gaps.

The selection survives a switch between kanban and list, which is how the
working flow ends: narrow on the board, switch to the list, tick rows, act.

### What the follow-up states are derived from

None of these is a stored status anyone has to maintain. Each is a question
asked of records the system already keeps:

| Filter | Derived from |
| --- | --- |
| Not contacted | `ggd_send_confirmed_at` is empty **and** `ggd_last_reply_received_at` is empty - Odoo has confirmed no send, and nobody has written in. A prepared draft is not contact and does not count. |
| Awaiting a reply | `ggd_delivery_status = accepted` **and** no reply recorded. The same domain as the review desk's *Sent, no reply yet*. |
| Follow-up due or late | Odoo's own `activity_state` is `today` or `overdue` - the next scheduled activity is due today or is late. |

And the two gaps: **Country missing** is an empty `country_id`; **Product
group missing** is `ggd_product_group_state = none`.

### Saving a view

The selection bar drives ordinary search filters, so Odoo's own favourites
save it:

1. Build the selection.
2. Open the search dropdown (the small caret at the right of the search box).
3. Under **Favorites**, type a name - `Türkiye - wire makers` - and save it.

A saved view is a live filter, not a snapshot: reopening it later includes
every matching opportunity created since. Reopen it from the same Favorites
list; rename or remove it with the pencil beside its name.

### The three bulk actions

Tick rows in the list, then **Actions**. Each one shows what is selected and
what will change before anything is written, and reports applied and blocked
counts with reasons afterwards. Blocked records are named as blocked - there
is no silent partial success - and only the ticked rows are ever touched.

1. **Add product groups.** Adds to whatever each opportunity already carries;
   it never replaces or removes. A `Do not contact` opportunity may still be
   classified - suppression stops outreach, not filing.
2. **Change stage.** Offers only the working stages, and applies the same
   rules the assistant is held to (issue #65): no won stage, and *Contacted*
   needs an Odoo-confirmed send or a recorded manual contact. *Reply
   Received*, *Won*, *Lost* and *Do Not Contact* are a person's decision on
   the opportunity itself and are not offered.
3. **Schedule a follow-up.** One activity per selected opportunity, with the
   type, responsible person, due date and summary you choose. It sends no
   email and starts no outbound workflow, and pressing Apply twice does not
   book it twice.

All three obey Odoo's own record access: an opportunity you may not write is
reported as blocked and left alone, whether the call comes from the button or
from the JSON-2 API.

### Classifying the records you already have

Nothing is guessed from the product-focus paragraph, so existing records
arrive unclassified and are meant to be worked through:

1. Open the pipeline and switch to the list.
2. **More > Product group missing** (and **Country missing** for the other
   gap).
3. Read the `Product / capability focus` column or open a record, then tick
   the rows that belong together.
4. **Actions > Add product groups**, pick the group, apply.
5. Repeat until the filter is empty. Country is edited on the opportunity's
   address, or on the linked company, as it always was.

Do the same with **Only archived product groups** after retiring a group, to
re-file the records it left behind.

## Recommended tags

Company type and lead source have fields of their own now (see the table
above); use those rather than a tag, so they can be counted. Tags stay useful
for everything that has no field:

- `Turkey to Germany`
- `Germany to Turkey`
- `Trade fair`
- `Inbound`
- `Referral`
- industry tags such as `Packaging`, `Machinery`, or `Building products`

Tags already on records are left exactly as they are; nothing was migrated or
deleted.

## Automation service user

n8n authenticates to Odoo with an API key. The JSON-2 endpoint
(`/json/2/crm.lead/<method>`) exposes every public method on the model, so the
access rights of the user that key belongs to are the only thing standing
between a compromised n8n and a compromised CRM. If the key belongs to the
administrator, the `Outreach approver` group protects nothing: a Settings user
can add itself to the group, and the superuser is exempt from every access rule
in Odoo.

So the key must belong to a dedicated internal user with CRM access and nothing
else. Kaan does every step that touches a key value; no agent ever sees one.

### Create the user

Settings > Users & Companies > Users > New:

- **Name** `GGD Automation (n8n)`, **login** `n8n@ggd.local`. The address needs
  no mailbox; the account never sends mail itself.
- **Access Rights**: Sales = `User: All Documents`. The workflows `search_read`
  leads they do not own, so `User: Own Documents Only` is not enough.
- Leave every other application blank. In particular: no `Administration`
  (Settings), no `Sales: Administrator`.
- Under the `Germany Growth Desk` heading, leave `Outreach approver`
  **unticked**. Since addon 19.0.1.11.0 only members of that group can approve
  outreach or clear `Do not contact`; the addon refuses the write for everyone
  else. Keeping the automation user out of the group is what makes "the LLM
  never approves" a property of Odoo, not of the workflow JSON.
- Set a long unique password on the account (Kaan needs it once, to log in as
  that user and issue the key).

Human approvers are added to `Outreach approver` in the same place. The
administrator is put in the group by the addon so an upgrade cannot lock the
owner out.

### Issue its key and hand it to n8n

1. Log in as `n8n@ggd.local`.
2. Preferences > Account Security > New API Key. Name it `n8n-YYYY-MM` and
   pick the **longest duration Odoo offers this account**.

   Odoo only shows the *Persistent key* (never expires) option to users with
   Settings rights, which the automation user deliberately does not have. So
   this key will always carry an expiry date - on 4 September 2026 the offered
   maximum produced `2026-12-03`. This matters: Odoo's `@api.autovacuum`
   DELETES a key whose `expiration_date` has passed, so the key stops
   authenticating and then disappears. That is exactly how Workflow 2 died on
   27 August, with `401 Unauthorized: Invalid apikey` on its first node.

   Write the expiry date in the calendar with a reminder two weeks before, and
   check it with `./scripts/check-odoo-api-keys.sh`, which prints the expiry of
   every key. An expiring automation key is not a defect to design around; it
   is a date to keep.
3. Copy the value once - triple-click to select the whole key rather than
   dragging across it; a half-selected key produces the same `Invalid apikey`
   401 as no key at all, which cost an afternoon on 4 September. Paste it into
   the n8n `Header Auth account` credential as `Bearer <key>`, one space after
   `Bearer`. It is never written to a file in this repository, a workflow
   export, a log, or a chat message.

### Verify before revoking anything

With the new credential in place, run all six workflows and confirm at least:

- **GGD-01** writes a research result onto a lead;
- **GGD-03** claims a send key;
- **GGD-04** sets `Do not contact` from an unsubscribe reply;
- **GGD-00**, **GGD-02** and **GGD-05** complete without a 401 or an
  access-rights error.

Then confirm the boundary actually holds: as the automation user, try to
approve a lead. It must fail. If it succeeds, the user is in `Outreach
approver` or has Settings rights, and the fix is not done.

### Revoke the old key

Only once the six workflows are green: open the previous key owner's
Preferences > Account Security and delete the old key. Any key still owned by
the administrator is deleted too - a key that exists is a key that can be used.

### Check and rotate

Two read-only scripts report on keys without ever reading a key value, so their
output is safe to paste into a ticket:

```bash
./scripts/check-odoo-api-keys.sh          # id, name, owner login, scope, expiry
./scripts/check-odoo-automation-user.sh   # owner login, groups, PASS/FAIL per key
```

Rotate the key before its expiry date - which, per the note above, the
automation user's key always has - and immediately if it may have been
exposed - a shared screenshot, a pasted log, a laptop handed on, a departing
contractor. Rotation is the same sequence: issue a new key on the same user,
swap the n8n credential, verify the six workflows, delete the old key, re-run
both scripts.

Disable the account the moment the automation is retired, and review the lead
chatter periodically: every automated write is attributed to this user, so the
audit trail names it.

## Reporting user for the ChatGPT desktop app

The ChatGPT/Codex desktop app reads this CRM through a local MCP connector
(ticket #59). It authenticates as a **second** dedicated user, entirely
separate from the n8n one above: `GGD Reporting (ChatGPT)`, login
`chatgpt@ggd.local`, with Sales = `User: All Documents` and nothing else. Like
the automation user it is deliberately **not** in `Outreach approver`, so it
can report and qualify but can neither approve outreach nor clear
`Do not contact`, and `crm.lead` unlink is a Sales Administrator right it does
not hold either.

Its key is created and rotated exactly as the automation key is, with the same
expiry caveat - Odoo offers a persistent key only to Settings users - and lives
in the macOS login Keychain rather than in an n8n credential. The n8n user, its
key and its credential are untouched by that setup.

Both users appear in `./scripts/check-odoo-api-keys.sh` and
`./scripts/check-odoo-automation-user.sh`. Full procedure, daily prompts,
renewal and revocation: `docs/CHATGPT-MCP-CONNECTOR.md`.

## First test record

Create a fictional company and move it through the pipeline. Verify:

1. fit score rejects values below 0 or above 100;
2. AI confidence rejects values below 0 or above 1;
3. approval fails when contact basis is blank, and when the basis note is
   under 20 characters;
4. approval fails when `Do not contact` is selected, and a user outside the
   "Outreach approver" group cannot approve at all;
5. selecting `Do not contact` revokes an existing approval;
6. approval and revocation appear in the chatter.

