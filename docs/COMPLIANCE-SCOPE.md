# Compliance scope — what this system is and is not built for

Status: **decision record**. Decided by Can on 2 September 2026. Supersedes
every earlier statement in this repository that a first email must be
"lawful under UWG §7", that a GDPR balancing note is owed, or that a lawyer
must review the contact procedure.

## The decision

**The product is going to be operated in a market outside the European
Union, where the German UWG §7 rule on marketing email and the GDPR do not
apply.** Development is therefore not constrained by either. Nobody working
on this repository — Kaan, Can, or an agent — should add, keep, or scope work
because of GDPR, UWG, ePrivacy, or a German lawyer's sign-off.

Concretely, the following are **out of scope** and are not to be built or
scheduled:

- lawyer review of the contact procedure (already dropped by Kaan on
  1 September 2026; this record makes it final and gives the reason);
- GDPR Art. 6(1)(f) balancing notes, Art. 14 information texts, records of
  processing, data-subject request handling;
- consent capture, double opt-in, "soft opt-in" condition tracking;
- retention schedules or deletion routines justified by data-protection law;
- purging prospect data from Git history *as a compliance measure* (it stays
  a data-hygiene rule, see below).

## What stays, and why it is not a compliance feature

The outbound gate in `odoo/addons/ggd_crm` stays exactly as it is. It was
designed with German law in mind, but every part of it earns its place on
operational grounds alone:

| Control | Operational reason |
| --- | --- |
| Human approval bound to a draft version and a recipient | The LLM drafts; a person decides. That is the product's promise and the only defence against a wrong email leaving under the company's name. |
| `ggd_do_not_contact` stops every send and follow-up | Someone who asked to be left alone and is emailed again reports spam. Spam reports are what get a cold domain blocked by the mail provider, and Zoho's terms require honouring opt-outs. |
| `ggd_contact_basis` plus an evidence note before approval | Provenance. It records *where this address came from* so a reply, a complaint, or a bounce can be traced to its source list. It also keeps the operator honest about list quality, which is what decides deliverability. |
| Send key claimed under a row lock, uncertain sends never retried | Idempotency. One approval, one email. |
| Hard bounces end sending to that address | Sender reputation, nothing else. |

The contact-basis vocabulary (`consent`, `existing_customer`, `inbound`,
`trade_fair`, `trade_fair_no_optin`, `referral`, `other`) is kept as a
**provenance record**. Since 2 September 2026 **every value may be approved
for email** once the note carries checkable evidence; the three values that
used to be blocked (`referral`, `trade_fair_no_optin`, `other`) were blocked
only because of UWG §7. The basis is provenance, the note is the evidence,
the approver is the decision.

Two controls were added the same day, both operational:

| Control | What it does |
| --- | --- |
| **Outreach approver group** (`ggd_crm.group_ggd_outreach_approver`) | Only its members may approve outreach or clear *Do not contact*. Setting *Do not contact* stays open to everyone, so the reply workflow can still act on an unsubscribe. The administrator is a member after upgrade; **the n8n service user must never be**. Enforced in `write()`/`create()`, not only on the button. |
| **Daily send cap** (system parameter `ggd_crm.daily_send_cap`, default 20) | `ggd_claim_send_key` refuses once that many claims exist in the trailing 24 hours, across all leads, under an advisory lock so concurrent claims cannot slip past it. `0` stops all sending; an unreadable value fails closed. This is the server-side ceiling on what an accidentally published send workflow can do to a cold domain. |

## Data hygiene rules that remain

These come from the repository's own engineering rules in `AGENTS.md`, not
from data-protection law, and they stay in force:

- no real prospect data, credentials, or tokens in Git-tracked files, logs,
  screenshots, or workflow exports;
- no email leaves without the outbound gate;
- only the owner's own test addresses until a production recipient is
  explicitly approved.

## Reading the older documents

Documents written between 16 August and 1 September 2026 refer to UWG §7,
GDPR, "lawful basis", and "legal review". They were correct for the market the
system was first aimed at and are kept unchanged where they are evidence logs
or historical status (`NEXT-ACTIONS.txt`, `docs/handoffs/`, `docs/QA-*`,
`docs/PROJECT-COMPLETION-STATUS.md`, `docs/COMPLETION-ROADMAP.md`,
`docs/STRATEGIC-REPORT-NEXT-MOVE.md`). Read every legal reference in them as
**"no longer applies"**. `docs/LAWFUL-CONTACT-PROCEDURE.md` is kept as the
reference for what the contact-basis field was designed to mean; its legal
sections are superseded, its operator checklist is still useful as a
list-quality checklist.

Living documents (`README.md`, `PLAN.md`, `AGENTS.md`, `GO-LIVE-PLAN.md`,
`docs/PROJECT-STATUS.md`) have been updated to point here.

## Decided the same day

Whether `referral`, `trade_fair_no_optin`, and `other` should remain blocked
from email approval was left open in the morning and **decided by Can in the
afternoon: the block is removed** (addon 19.0.1.11.0). The values stay as
provenance; approval needs the evidence note and an approver, nothing else.
