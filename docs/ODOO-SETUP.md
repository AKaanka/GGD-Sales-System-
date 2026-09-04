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

## Recommended tags

- `Turkey to Germany`
- `Germany to Turkey`
- `Manufacturer`
- `Distributor`
- `Trade fair`
- `Inbound`
- `Referral`
- industry tags such as `Packaging`, `Machinery`, or `Building products`

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

