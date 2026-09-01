# Gate 3 — Workflow 4 test payloads

Documented, ready-to-use test inputs for manually triggering Workflow 4
(reply and bounce intake) against the fixtures created by
`./scripts/create-gate3-fixtures.sh`. This file only documents test data; it
does not import, edit, or execute any workflow. Feed these values into
Workflow 4's manual trigger node the same way the existing
`workflows/test-inputs-workflow3.json` fixtures are used for Workflow 3.

Run the fixture script first and confirm FX2, FX5, FX6A/FX6B exist before
using these payloads. All addresses/IDs below are fictional (`.invalid`
domain) and match what the fixture script created.

## 1. Matched by sender email (category: interested)

Exercises the normal sender-email match path (`ggd_find_reply_candidates`
with no `in_reply_to`). Matches FX2 only — FX2's email is not shared with
any other fixture.

```json
{
  "sender_email": "fx2@ggd-gate3-fixture.invalid",
  "in_reply_to": "",
  "subject": "Re: Fixture subject: Introduction from Germany Growth Desk",
  "category": "interested",
  "summary": "Fixture reply: recipient asks for a short call next week.",
  "suggested_next_action": "Fixture: propose two call times.",
  "confidence": 0.88,
  "received_at": "2026-08-26T09:00:00Z",
  "reply_message_id": "<gate3-fixture-reply-fx2-001@ggd-gate3-fixture.invalid>"
}
```

Expected: one candidate, `match_type: "sender"`, record updates via
`ggd_record_reply`, `ggd_reply_needs_review` stays false (confidence >= 0.7).

## 2. Matched by Message-ID (category: meeting)

Exercises the exact-match path, which takes priority over sender-email
matching. Matches FX5, whose synthetic sent-state carries a known
Message-ID.

```json
{
  "sender_email": "fx5@ggd-gate3-fixture.invalid",
  "in_reply_to": "<gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>",
  "subject": "Re: Fixture subject: Germany Growth Desk introduction (synthetic sent fixture)",
  "category": "meeting",
  "summary": "Fixture reply: recipient wants to schedule a meeting.",
  "suggested_next_action": "Fixture: propose meeting dates.",
  "confidence": 0.92,
  "received_at": "2026-08-26T09:05:00Z",
  "reply_message_id": "<gate3-fixture-reply-fx5-001@ggd-gate3-fixture.invalid>"
}
```

Expected: `match_type: "message_id"`, exactly one candidate (FX5).

## 3. Unmatched inbound

No fixture uses this sender address or Message-ID on purpose — this should
fall through to `ggd_queue_unmatched_inbound`, which creates its own new
manual-review record (do not pre-create anything for this case).

```json
{
  "sender_email": "unknown-sender@ggd-gate3-fixture.invalid",
  "in_reply_to": "<not-a-real-thread@ggd-gate3-fixture.invalid>",
  "subject": "Re: something we never sent",
  "reason": "Fixture: no In-Reply-To or sender match found in Odoo.",
  "received_at": "2026-08-26T09:10:00Z"
}
```

Expected: a new `crm.lead` named "Manual inbound review: ..." with
`ggd_reply_needs_review` and `ggd_automation_needs_review` both true, and a
To-Do activity scheduled. Re-running with the same `message_id` must not
create a second review record (see the `existing` guard in
`ggd_queue_unmatched_inbound`).

## 4. Ambiguous match (two candidates)

FX6A and FX6B deliberately share one email address so the sender-email
search returns two candidates.

```json
{
  "sender_email": "fx6-ambiguous@ggd-gate3-fixture.invalid",
  "in_reply_to": "",
  "subject": "Re: fixture ambiguous contact",
  "reason": "Fixture: sender email matches more than one Odoo record.",
  "received_at": "2026-08-26T09:15:00Z"
}
```

Expected: `ggd_find_reply_candidates` returns `match_type: "sender"` with two
`candidates` (FX6A and FX6B). Workflow 4 should route this to manual review
rather than guessing which record to update — confirm that branch, do not
call `ggd_record_reply` against either candidate automatically.

## 5. Unsubscribe (run after test #1, same lead)

Reuses FX2 with a later `received_at` than test #1, so it is not dropped as
a stale/older reply.

**Timestamp corrected 27 August 2026.** This payload originally carried
`2026-08-26T10:00:00Z`. Gate 3 step 4 scenario 1 has since recorded a reply
on FX2 with `ggd_last_reply_received_at = 2026-08-26 17:15:00`, and
`ggd_record_reply` drops any reply older than the one already stored (see
`test_older_reply_does_not_replace_latest_reply_state`). At the original
timestamp this scenario would have been silently discarded as out-of-order
and would have looked like a passing no-op rather than a real unsubscribe
test. The timestamp is now `2026-08-27T12:00:00Z`. If FX2 is ever reset and
scenario 1 re-run, re-check that this stays the later of the two.

```json
{
  "sender_email": "fx2@ggd-gate3-fixture.invalid",
  "in_reply_to": "",
  "subject": "Re: Fixture subject: Introduction from Germany Growth Desk",
  "category": "unsubscribe",
  "summary": "Fixture reply: recipient asks to stop receiving emails.",
  "suggested_next_action": "Fixture: no further outbound action.",
  "confidence": 0.95,
  "received_at": "2026-08-27T12:00:00Z",
  "reply_message_id": "<gate3-fixture-reply-fx2-002@ggd-gate3-fixture.invalid>"
}
```

Expected: `ggd_do_not_contact` becomes true on FX2, `ggd_suggested_next_action`
is overwritten with the suppressed-contact message, `ggd_response_draft` and
`ggd_suggested_follow_up_at` are cleared. Confirm no further outbound path
treats FX2 as contactable afterward.

## 6. Bounce (hard bounce)

Matches FX5's synthetic sent state. `ggd_record_bounce` requires
`ggd_send_confirmed_at` to already be set and `message_id` to exactly equal
`ggd_last_message_id` — both true for FX5 only.

```json
{
  "message_id": "<gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>",
  "summary": "Fixture: simulated hard bounce, mailbox does not exist (550).",
  "hard_bounce": true
}
```

Expected: FX5's `ggd_delivery_status` becomes `bounced`,
`ggd_delivery_needs_review` becomes true, and — because `hard_bounce` is
true — `ggd_do_not_contact` becomes true. Calling this against any other
fixture (no confirmed send / mismatched Message-ID) must raise a
`ValidationError`, which is itself worth confirming once as a negative test.

## Notes

- None of these payloads send email or touch Zoho/n8n credentials; they are
  Odoo-side method inputs for whatever manually triggers Workflow 4's logic
  during Gate 3 testing.
- Re-running scenario 1 or 2 with the same `reply_message_id` a second time
  should be a no-op (`ggd_record_reply` treats a repeated Message-ID as
  already processed) — worth confirming as a dedup test.
- If Kaan or Codex later decide the `crm.stage` records from
  `docs/ODOO-SETUP.md` don't exist yet, `create-gate3-fixtures.sh` still
  succeeds; the fixtures are simply left without a `stage_id`.
- FX7 ("Stale Confirmed Send, For Follow-Up Queue Test") is not used by
  any scenario above — it exists for **Workflow 5**, not Workflow 4. It is
  built exactly like FX5 (real `ggd_claim_send_key`/`ggd_finalize_send`,
  its own synthetic Message-ID
  `<gate3-fixture-fx7-001@ggd-gate3-fixture.invalid>`, no SMTP call), then
  `ggd_send_confirmed_at`, `ggd_last_sent_at`, and `ggd_last_message_date`
  are backdated by 8 days in a separate write so it clears both the 7-day
  staleness filter in `workflows/GGD-05-daily-follow-up.json`'s candidate
  query domain and `ggd_queue_follow_up()`'s own "not yet seven days old"
  guard. No reply is recorded for FX7, so it should surface as a Workflow
  5 follow-up candidate; running `ggd_queue_follow_up()` against it twice
  should create one activity on the first call and be a no-op on the
  second (`ggd_last_follow_up_queue_key` dedup) — worth confirming as a
  dedup test alongside FX7's staleness eligibility itself.

---

## Raw email payloads (Workflow 4 manual trigger / IMAP shape)

The six scenarios above are Odoo-method-level test inputs. The workflow's
actual entry point is different: `workflows/GGD-04-reply-and-bounce-intake.json`'s
"Normalize and sanitize inbound email" node (read-only reference, not edited
by this script) takes a raw email object shaped like
`{from, subject, messageId, inReplyTo, textPlain, date}` (also accepts
`text`/`html`/`textHtml` for the body and reads `references`/headers as a
fallback) and derives `sender`, `message_id`, `in_reply_to`, `body`,
`is_bounce`, and `hard_bounce` from it before Odoo matching ever runs. Use
these payloads to test that node directly, e.g. via Workflow 4's manual
pinned-email test input. Same fixtures, same six scenarios, different shape.

Bounce detection (from the node's own logic, for reference):

- `is_bounce` is true when the sender, subject, or first 2000 characters of
  the body match `mailer-daemon`, `postmaster`, `delivery status
  notification`, `undeliverable`, `returned mail`, `mail delivery failed`,
  or `recipient address rejected` (case-insensitive).
- `hard_bounce` is `is_bounce` AND none of `mailbox full`, `temporar...`,
  `try again`, `greylist` appear (those mark a soft bounce instead).
- When there is no explicit `inReplyTo`/`references` header, the node pulls
  the original outbound Message-ID out of the body from an
  `Original-Message-ID:` or `X-Original-Message-ID:` DSN line — this is how
  a bounce gets matched back to the send that produced it.

### 1. Matched by sender email (category: interested)

```json
{
  "from": "Fictional Buyer <fx2@ggd-gate3-fixture.invalid>",
  "subject": "Re: Fixture subject: Introduction from Germany Growth Desk",
  "messageId": "<gate3-fixture-reply-fx2-001@ggd-gate3-fixture.invalid>",
  "inReplyTo": "",
  "textPlain": "Fixture reply text (not real): thanks for reaching out, could we do a short call next week?",
  "date": "2026-08-26T09:00:00Z"
}
```

### 2. Matched by Message-ID (category: meeting)

```json
{
  "from": "Fictional Contact <fx5@ggd-gate3-fixture.invalid>",
  "subject": "Re: Fixture subject: Germany Growth Desk introduction (synthetic sent fixture)",
  "messageId": "<gate3-fixture-reply-fx5-001@ggd-gate3-fixture.invalid>",
  "inReplyTo": "<gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>",
  "textPlain": "Fixture reply text (not real): yes, let's set up a meeting.",
  "date": "2026-08-26T09:05:00Z"
}
```

`inReplyTo` here must equal FX5's `FX5_MESSAGE_ID` as printed by
`create-gate3-fixtures.sh` (`<gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>`
unless the domain constant in the script changes).

### 3. Unmatched inbound

```json
{
  "from": "Unknown Fictional Sender <unknown-sender@ggd-gate3-fixture.invalid>",
  "subject": "Re: something we never sent",
  "messageId": "<gate3-fixture-reply-unmatched-001@ggd-gate3-fixture.invalid>",
  "inReplyTo": "<not-a-real-thread@ggd-gate3-fixture.invalid>",
  "textPlain": "Fixture reply text (not real): no Odoo record should match this sender or Message-ID.",
  "date": "2026-08-26T09:10:00Z"
}
```

### 4. Ambiguous match (two candidates)

```json
{
  "from": "Fictional Duplicate Contact <fx6-ambiguous@ggd-gate3-fixture.invalid>",
  "subject": "Re: fixture ambiguous contact",
  "messageId": "<gate3-fixture-reply-fx6-001@ggd-gate3-fixture.invalid>",
  "inReplyTo": "",
  "textPlain": "Fixture reply text (not real): sender email matches both FX6A and FX6B.",
  "date": "2026-08-26T09:15:00Z"
}
```

### 5. Unsubscribe (run after test #1, same lead)

```json
{
  "from": "Fictional Buyer <fx2@ggd-gate3-fixture.invalid>",
  "subject": "Re: Fixture subject: Introduction from Germany Growth Desk",
  "messageId": "<gate3-fixture-reply-fx2-002@ggd-gate3-fixture.invalid>",
  "inReplyTo": "",
  "textPlain": "Fixture reply text (not real): please remove me from your list, unsubscribe.",
  "date": "2026-08-27T12:00:00Z"
}
```

### 6. Hard bounce

Sender is `mailer-daemon`-shaped and the body carries an
`Original-Message-ID:` DSN line pointing at FX5's outbound Message-ID, so
the node both flags this as a bounce and matches it back to FX5 by exact
Message-ID (a bounce is only accepted as matched when `match_type` is
`message_id` — a sender-only match is not enough, per the matching node's
`exactEnough` check). No soft-bounce wording appears, so this resolves as a
hard bounce.

```json
{
  "from": "Mail Delivery System <mailer-daemon@ggd-gate3-fixture.invalid>",
  "subject": "Undeliverable: Fixture subject: Germany Growth Desk introduction (synthetic sent fixture)",
  "messageId": "<gate3-fixture-bounce-fx5-001@ggd-gate3-fixture.invalid>",
  "inReplyTo": "",
  "textPlain": "This is an automatically generated Delivery Status Notification.\n\nDelivery to the following recipient failed permanently:\n\n    fx5@ggd-gate3-fixture.invalid\n\nTechnical details: 550 5.1.1 recipient address rejected (fixture, not a real bounce).\n\nOriginal-Message-ID: <gate3-fixture-fx5-001@ggd-gate3-fixture.invalid>",
  "date": "2026-08-26T09:20:00Z"
}
```
