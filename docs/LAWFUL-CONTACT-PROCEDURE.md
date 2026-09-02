# Lawful Contact Procedure and Production Recipient Checklist

> **Superseded on 2 September 2026 — read [COMPLIANCE-SCOPE.md](COMPLIANCE-SCOPE.md) first.**
> The product will be operated outside the EU. Sections 2 (legal framework),
> 3 (the UWG finding) and every GDPR item in the checklists **no longer
> apply**, and no lawyer review is planned. The document is kept because it
> defines what each `ggd_contact_basis` value was meant to record and because
> its recipient checklist doubles as a list-quality checklist. The addon's
> enforcement described in section 8 is unchanged, for the operational reasons
> given in COMPLIANCE-SCOPE.md.

Status: **draft for review**. Owner: Kaan Kadıoğlu, Germany Growth Desk.
Created 16 August 2026. This document addresses item 8 of
[PROJECT-STATUS.md](PROJECT-STATUS.md), but that item remains open until a
qualified German lawyer has reviewed and approved this procedure.

This is an operating procedure, not legal advice. It must be reviewed by a
lawyer qualified in German competition and data-protection law before the first
real prospect is contacted. Nothing in this document makes an otherwise
impermissible email lawful.

## 1. Why this document exists

The system already enforces a *technical* gate: `ggd_outreach_approved == true`,
`ggd_do_not_contact == false`, and a non-empty `ggd_contact_basis`. That gate
proves a human clicked approve. It does not prove the email was lawful to send.
This procedure defines what the human must verify **before** clicking approve.

## 2. Legal framework in one page

Two separate bodies of law apply at the same time. Satisfying one does not
satisfy the other.

### 2.1 UWG § 7 — unfair commercial practices (the harder gate)

- **§ 7 Abs. 2 Nr. 2** treats advertising by electronic mail without the
  recipient's **prior express consent** as unreasonable harassment.
- This applies **identically to B2B and B2C**. There is no business exemption.
  A marketing email to a purchasing manager at a company address is treated the
  same as one to a private individual.
- An unsubscribe link does **not** cure a missing consent.
- Note the asymmetry with telephone: § 7 Abs. 2 Nr. 1 permits *presumed*
  consent (*mutmaßliche Einwilligung*) for B2B calls where there are concrete
  indications the business would welcome the call. **No equivalent presumption
  exists for email.**

### 2.2 UWG § 7 Abs. 3 — the existing-customer exception ("soft opt-in")

Email without express consent is permissible only where **all four** conditions
hold cumulatively:

1. the address was obtained **in connection with the sale** of goods or services
   to that customer;
2. it is used to advertise the seller's **own similar** goods or services;
3. the customer **has not objected**; and
4. the customer was **clearly informed**, both at collection and in every
   message, of the right to object at any time at no cost beyond base
   transmission rates.

If any one of the four fails, the exception does not apply.

### 2.3 GDPR — processing the personal data

Separately from UWG, holding and processing a named person's business email is
processing of personal data. In practice the basis is legitimate interest under
**Art. 6(1)(f)**, which requires a documented balancing test. Where the data was
not collected from the person directly (research, scraping, list purchase),
**Art. 14** information duties are triggered — the person must normally be
informed, generally within one month.

A legitimate-interest basis under GDPR does **not** substitute for UWG consent.

## 3. Material finding — the contact-basis field overstates permission

`ggd_contact_basis` in `odoo/addons/ggd_crm/models/crm_lead.py` currently
offers: `consent`, `existing_customer`, `inbound`, `trade_fair`, `referral`,
`other`.

Selecting `trade_fair` or `referral` is enough to pass the technical approval
gate. But under § 7 Abs. 2 Nr. 2, "we met at a trade fair" and "someone
introduced us" are **not** by themselves lawful bases for a marketing email.
They are *sources of a contact*, not *consents to be emailed*. The field, as
written, invites the operator to approve a send that the law does not permit.

**Decision:** the values stay (they are useful provenance), but the procedure
below classifies each one as SEND / DO NOT SEND, and the operator must record
the underlying evidence, not merely pick a label. Section 8 proposes a code
change to enforce this.

## 4. Contact-basis decision table

| `ggd_contact_basis` | May a first marketing email be sent? | Evidence required in `ggd_contact_basis_note` |
| --- | --- | --- |
| `consent` | **Yes**, if consent is provable | Where, when, and how consent was given; exact wording shown; opt-in record or screenshot reference |
| `existing_customer` | **Yes**, only if all four § 7 Abs. 3 conditions hold | Contract/invoice reference; confirmation the offer is a *similar own* service; confirmation objection notice was given at collection and appears in this message |
| `inbound` | **Yes**, if the enquiry covers this subject | Date and channel of enquiry; quoted request; confirmation the reply stays within its scope |
| `trade_fair` | **No — unless** an explicit opt-in was recorded at the stand | Fair name and date; card/scan reference; **the consent wording signed or ticked**. Absent that wording: DO NOT SEND |
| `referral` | **No** | A referral is not consent. Route to phone or ask the referrer for an introduction instead |
| `other` | **No** | Requires written legal review before use. Record the reviewer and date |

Where the table says **No**, `ggd_outreach_approved` must remain false.
Possible alternatives include a telephone call, platform message, warm
introduction, or postal letter. None is automatically permitted: each channel
requires its own legal and factual review before use.

## 5. Pre-import checklist (run once per prospect list)

Before any real record enters Odoo:

- [ ] Source of the list is documented and lawful; no purchased or scraped
      address list is imported for email use.
- [ ] Every record carries a `ggd_contact_basis` and supporting note.
- [ ] Records with basis `referral` or `other` are imported with
      `ggd_do_not_contact = true` until reviewed.
- [ ] Named individuals are identified. Role addresses such as
      `info@`/`kontakt@` are reviewed separately; they can still involve
      personal data depending on how they are assigned, monitored, and used.
- [ ] An Art. 14 information text exists and a plan for delivering it is agreed.
- [ ] A GDPR Art. 6(1)(f) balancing note is written for the list as a whole.
- [ ] Retention period for non-responding prospects is set and recorded.

## 6. Per-record approval checklist (run before every first send)

The person clicking **Approve Outreach** confirms:

- [ ] `ggd_do_not_contact` is false.
- [ ] `ggd_contact_basis` is one of the SEND rows in section 4.
- [ ] `ggd_contact_basis_note` contains the specific evidence that row requires
      — a date, a source, a document reference. Not a restatement of the label.
- [ ] The evidence is verifiable today, not remembered.
- [ ] The recipient address is a real, correctly attributed business address.
- [ ] The draft names the sender, Germany Growth Desk, and a working reply path.
- [ ] The draft carries a clear, free objection/unsubscribe route.
- [ ] The draft's subject line is not misleading as to its commercial nature.
- [ ] Imprint/contact details required for commercial communication are present.
- [ ] The claim set in the draft is factual; no invented reference customers.
- [ ] For `existing_customer`: the offer really is a *similar own* service.

If any box fails, revoke approval rather than editing around it.

## 7. Suppression and objection handling

- Any objection, unsubscribe, or "stop" — however phrased, in any language —
  sets `ggd_do_not_contact = true` immediately. Workflow 4 already does this on
  category `unsubscribe`; ambiguous phrasing goes to manual review and is
  treated as an objection until a human decides otherwise.
- Suppression is permanent and survives re-import. Never clear
  `ggd_do_not_contact` to re-enable a previously objecting contact.
- A bounce is not an objection, but a hard bounce ends further sending to that
  address.
- Objections are honoured at the level of the **person and the company**, unless
  the objection is clearly personal only.
- Record the date and the message that triggered suppression in the chatter.

## 8. Proposed code change (tracked separately)

To stop the field from implying permission it does not grant:

1. Relabel the selection values to state their effect, e.g.
   `trade_fair` → "Trade fair — opt-in recorded at stand" and add
   `trade_fair_no_optin` → "Trade fair — no opt-in (do not email)".
2. Extend `action_ggd_approve_outreach` to refuse approval when the basis is in
   a `NO_EMAIL_BASES` set, mirroring the existing `ggd_do_not_contact` guard.
3. Require `ggd_contact_basis_note` to be non-empty before approval.
4. Add a `ggd_contact_basis_verified_at` datetime, set only by the approving
   human, so evidence age is visible.

Each change is a small, testable edit to `crm_lead.py` plus the six control
tests in [ODOO-SETUP.md](ODOO-SETUP.md).

## 9. Before the first real send

1. This document reviewed and signed off by a qualified German lawyer.
2. Section 8 code changes implemented and their tests passing.
3. Remaining QA in [PROJECT-STATUS.md](PROJECT-STATUS.md) items 2–7 complete.
4. First production send is a single record, sent manually, reviewed after.
5. No workflow that can send email is activated for unattended running until
   at least ten supervised sends have been reviewed without a finding.

## 10. Review triggers

Re-review this procedure when: the law or guidance changes; a new prospect
source is introduced; a complaint or warning letter (*Abmahnung*) is received;
the offer changes such that "similar own services" no longer holds; or twelve
months pass, whichever comes first.

## Primary sources for legal review

- Official German statutory text, UWG § 7:
  https://www.gesetze-im-internet.de/uwg_2004/__7.html
- Official EU text, General Data Protection Regulation:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679

These links are starting points, not legal approval. The reviewing lawyer must
confirm the current versions, document the review date, and record any required
changes before production outreach.
