#!/bin/bash
# Odoo-side smoke test for the five addon methods that Workflows 4 and 5 call.
#
# Usage:
#   ./scripts/smoke-test-odoo-methods.sh
#
# Why this exists
# ---------------
# The 102 addon unit tests all run inside Odoo's TransactionCase, which rolls
# back. Nothing they exercise is ever committed. This script drives the same
# methods against REAL, COMMITTED records, which is the state Workflows 4 and 5
# actually operate on:
#
#   ggd_find_reply_candidates   ggd_record_reply      ggd_record_bounce
#   ggd_queue_follow_up         ggd_queue_unmatched_inbound
#
# Safety
# ------
# * Creates its OWN throwaway records under a unique per-run name prefix and a
#   unique per-run .invalid email domain. It never reads, writes, or depends on
#   the Gate 3 fixtures (FX1-FX7), so it can run alongside Gate 3 work.
# * Sends no email. No SMTP is involved anywhere: the "confirmed sent" state is
#   reached through ggd_claim_send_key/ggd_finalize_send, neither of which
#   contacts a mail server.
# * Archives (active=False) every record it created at the end. It never
#   deletes anything.
# * Read-only with respect to every pre-existing record in the database.
#
# Exit code is 0 only when every check passes.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start the normal Odoo service first (docker compose up -d), then re-run." >&2
  exit 1
fi

LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

echo "GGD Odoo method smoke test"
echo "=========================================================="

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF' | tee "$LOG"
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError

Lead = env["crm.lead"]
Activity = env["mail.activity"]

RUN = datetime.now().strftime("%Y%m%d%H%M%S")
PREFIX = "[GGD-SMOKE %s]" % RUN
DOMAIN = "ggd-smoke-%s.invalid" % RUN
NOTE = (
    "Smoke-test evidence only (not real): simulated opt-in via the GGD "
    "website contact form, reference SMOKE-%s." % RUN
)
T0 = datetime.now().replace(microsecond=0)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


results = []
created_ids = []


def check(name, condition, detail=""):
    ok = bool(condition)
    results.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (
        (" | " + str(detail)) if (detail and not ok) else ""
    ))
    return ok


def expect_raises(name, fn):
    """A refusal is the feature. Anything other than ValidationError is a bug."""
    try:
        fn()
    except ValidationError:
        outcome = check(name, True)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, reported
        outcome = check(name, False, "wrong exception %s: %s" % (type(exc).__name__, exc))
    else:
        outcome = check(name, False, "no exception was raised")
    try:
        env.invalidate_all()
    except Exception:
        pass
    return outcome


def new_lead(tag, **vals):
    slug = tag.lower().replace(" ", "-")
    base = {
        "name": "%s %s" % (PREFIX, tag),
        "type": "opportunity",
        "email_from": "%s@%s" % (slug, DOMAIN),
        "description": "GGD smoke-test record. Fictional. Archived automatically.",
    }
    base.update(vals)
    lead = Lead.create(base)
    created_ids.append(lead.id)
    return lead


def sent_lead(tag, **vals):
    """Walk the real approve -> claim -> finalize path. No SMTP, no email."""
    lead = new_lead(tag, **vals)
    lead.ggd_prepare_draft(
        "Smoke subject %s" % tag,
        "Smoke body for %s. This was never mailed to anyone." % tag,
    )
    lead.write({"ggd_contact_basis": "consent", "ggd_contact_basis_note": NOTE})
    lead.action_ggd_approve_outreach()
    lead.ggd_claim_send_key("%s:%s" % (lead.id, lead.ggd_approved_draft_version))
    message_id = "<smoke-%s-%s@%s>" % (RUN, lead.id, DOMAIN)
    lead.ggd_finalize_send(
        message_id,
        lead.ggd_approved_recipient,
        lead.ggd_draft_subject,
        "Smoke body summary.",
    )
    return lead, message_id


def activity_count(lead_id):
    return Activity.search_count(
        [("res_model", "=", "crm.lead"), ("res_id", "=", lead_id)]
    )


print("")
print("Run id %s, throwaway domain %s" % (RUN, DOMAIN))

# ---------------------------------------------------------------- A
print("")
print("--- A. ggd_find_reply_candidates (Workflow 4 matching) ---")

a1, a1_mid = sent_lead("A1 message-id match")
res = Lead.ggd_find_reply_candidates(in_reply_to=a1_mid)
check(
    "A1 exact Message-ID returns exactly one candidate, the right one",
    res.get("match_type") == "message_id"
    and len(res.get("candidates") or []) == 1
    and res["candidates"][0]["id"] == a1.id,
    res,
)

a2 = new_lead("A2 sender match")
res = Lead.ggd_find_reply_candidates(sender_email=a2.email_from)
check(
    "A2 unknown Message-ID falls back to sender-email match",
    res.get("match_type") == "sender"
    and any(c["id"] == a2.id for c in (res.get("candidates") or [])),
    res,
)

amb_email = "ambiguous@%s" % DOMAIN
a3a = new_lead("A3 ambiguous one", email_from=amb_email)
a3b = new_lead("A3 ambiguous two", email_from=amb_email)
res = Lead.ggd_find_reply_candidates(sender_email=amb_email)
check(
    "A3 shared address returns MORE than one candidate (ambiguous, must not auto-apply)",
    res.get("match_type") == "sender" and len(res.get("candidates") or []) >= 2,
    res,
)

res = Lead.ggd_find_reply_candidates(sender_email="nobody@%s" % DOMAIN)
check(
    "A4 unknown sender returns no match rather than a wrong one",
    res.get("match_type") == "none" and not (res.get("candidates") or []),
    res,
)

# ---------------------------------------------------------------- B
print("")
print("--- B. ggd_record_reply (Workflow 4 reply intake) ---")

b1, _ = sent_lead("B1 normal reply")
b1_rid = "<smoke-%s-reply-b1@%s>" % (RUN, DOMAIN)
applied = b1.ggd_record_reply(
    "interested",
    "Smoke: recipient asks for a short call.",
    "Smoke: propose two times.",
    0.9,
    response_draft="Smoke suggested response.",
    reply_message_id=b1_rid,
    received_at=iso(T0),
)
check(
    "B1 high-confidence reply is applied and needs no human review",
    applied is True
    and b1.ggd_reply_category == "interested"
    and not b1.ggd_reply_needs_review,
    "applied=%s category=%s" % (applied, b1.ggd_reply_category),
)
check(
    "B1 ISO-8601 'Z' timestamp from n8n is parsed and stored",
    bool(b1.ggd_last_reply_received_at)
    and b1.ggd_last_reply_received_at.strftime("%Y-%m-%dT%H:%M:%SZ") == iso(T0),
    b1.ggd_last_reply_received_at,
)
check(
    "B1 last message date tracks the reply (Workflow 5 depends on this)",
    str(b1.ggd_last_message_date) == T0.strftime("%Y-%m-%d"),
    b1.ggd_last_message_date,
)

duplicate = b1.ggd_record_reply(
    "objection",
    "Smoke: same Message-ID replayed.",
    "Smoke: should not apply.",
    0.9,
    reply_message_id=b1_rid,
    received_at=iso(T0 + timedelta(hours=2)),
)
check(
    "B2 replayed Message-ID is a no-op, prior analysis untouched",
    duplicate is False and b1.ggd_reply_category == "interested",
    "returned=%s category=%s" % (duplicate, b1.ggd_reply_category),
)

older = b1.ggd_record_reply(
    "objection",
    "Smoke: an older message arriving late.",
    "Smoke: should not apply.",
    0.9,
    reply_message_id="<smoke-%s-reply-b3@%s>" % (RUN, DOMAIN),
    received_at=iso(T0 - timedelta(hours=1)),
)
check(
    "B3 out-of-order older reply does not overwrite newer state",
    older is False and b1.ggd_reply_category == "interested",
    "returned=%s category=%s" % (older, b1.ggd_reply_category),
)

b4, _ = sent_lead("B4 low confidence")
low = b4.ggd_record_reply(
    "unclear",
    "Smoke: ambiguous wording.",
    "Smoke: needs a human.",
    0.3,
    reply_message_id="<smoke-%s-reply-b4@%s>" % (RUN, DOMAIN),
    received_at=iso(T0),
)
check(
    "B4 low confidence routes to human review",
    low is False and b4.ggd_reply_needs_review and b4.ggd_automation_needs_review,
    "returned=%s" % low,
)

b5, _ = sent_lead("B5 unsubscribe")
b5.ggd_record_reply(
    "unsubscribe",
    "Smoke: please stop emailing me.",
    "Smoke: no outbound action.",
    0.95,
    response_draft="This draft must be discarded.",
    reply_message_id="<smoke-%s-reply-b5@%s>" % (RUN, DOMAIN),
    received_at=iso(T0),
)
check("B5 unsubscribe sets Do not contact", b5.ggd_do_not_contact is True, b5.ggd_do_not_contact)
check(
    "B5 unsubscribe discards the suggested outbound response",
    not b5.ggd_response_draft,
    b5.ggd_response_draft,
)

# ---------------------------------------------------------------- C
print("")
print("--- C. ggd_record_bounce (Workflow 4 bounce handling) ---")

c1, c1_mid = sent_lead("C1 hard bounce")
bounced = c1.ggd_record_bounce(c1_mid, "Smoke: simulated 550 mailbox unavailable.", hard_bounce=True)
check(
    "C1 hard bounce is recorded against the matching send",
    bounced is True and c1.ggd_delivery_status == "bounced",
    c1.ggd_delivery_status,
)
check("C1 hard bounce suppresses all future contact", c1.ggd_do_not_contact is True)
check("C1 hard bounce raises a delivery review item", c1.ggd_delivery_needs_review is True)

c2, _ = sent_lead("C2 bounce mismatch")
expect_raises(
    "C2 bounce whose Message-ID matches nothing is refused",
    lambda: c2.ggd_record_bounce("<wrong-id@%s>" % DOMAIN, "Smoke mismatch.", hard_bounce=True),
)

# ---------------------------------------------------------------- D
print("")
print("--- D. ggd_queue_follow_up (Workflow 5 follow-up queue) ---")

d1, _ = sent_lead("D1 stale follow up")
expect_raises(
    "D1 a send from today is refused as not yet due",
    lambda: d1.ggd_queue_follow_up("Smoke follow-up draft."),
)
d1.write({"ggd_send_confirmed_at": fields.Datetime.now() - timedelta(days=8)})
queued = d1.ggd_queue_follow_up("Smoke follow-up draft.")
check(
    "D2 an 8-day-old send queues one follow-up",
    queued is True and bool(d1.ggd_last_follow_up_queue_key),
    "returned=%s key=%s" % (queued, d1.ggd_last_follow_up_queue_key),
)
count_after_first = activity_count(d1.id)
check("D2 exactly one review activity was created", count_after_first == 1, count_after_first)

again = d1.ggd_queue_follow_up("Smoke follow-up draft, second attempt.")
count_after_second = activity_count(d1.id)
check(
    "D3 a second run is deduplicated - still exactly one activity",
    again is False and count_after_second == 1,
    "returned=%s activities=%s" % (again, count_after_second),
)

d4, _ = sent_lead("D4 suppressed follow up")
d4.write({"ggd_send_confirmed_at": fields.Datetime.now() - timedelta(days=8)})
d4.write({"ggd_do_not_contact": True})
expect_raises(
    "D4 Do not contact blocks follow-up even when the send is stale",
    lambda: d4.ggd_queue_follow_up("Smoke."),
)

d5, _ = sent_lead("D5 replied follow up")
d5.write({"ggd_send_confirmed_at": fields.Datetime.now() - timedelta(days=8)})
d5.ggd_record_reply(
    "interested",
    "Smoke: they already replied.",
    "Smoke: handle the reply instead.",
    0.9,
    reply_message_id="<smoke-%s-reply-d5@%s>" % (RUN, DOMAIN),
    received_at=iso(T0),
)
expect_raises(
    "D5 a reply after the send blocks the follow-up",
    lambda: d5.ggd_queue_follow_up("Smoke."),
)

# ---------------------------------------------------------------- E
print("")
print("--- E. ggd_queue_unmatched_inbound (Workflow 4 manual-review queue) ---")

e_mid = "<smoke-%s-unmatched@%s>" % (RUN, DOMAIN)
e_id = Lead.ggd_queue_unmatched_inbound(
    e_mid,
    "stranger@%s" % DOMAIN,
    "Smoke: subject of an unmatched inbound email",
    "Smoke: no In-Reply-To or sender match was found in Odoo.",
)
if e_id:
    created_ids.append(e_id)
e_rec = Lead.browse(e_id)
check("E1 unmatched inbound creates a visible review record", bool(e_id) and bool(e_rec.exists()), e_id)
check(
    "E1 the review record is flagged for human review",
    e_rec.ggd_reply_needs_review and e_rec.ggd_automation_needs_review,
)
e_acts = activity_count(e_id)
check("E1 the review record carries a To-Do activity", e_acts == 1, e_acts)

e_id2 = Lead.ggd_queue_unmatched_inbound(
    e_mid,
    "stranger@%s" % DOMAIN,
    "Smoke: subject of an unmatched inbound email",
    "Smoke: the same message delivered twice.",
)
check(
    "E2 the same Message-ID does not create a second review record",
    e_id2 == e_id,
    "first=%s second=%s" % (e_id, e_id2),
)

# ---------------------------------------------------------------- cleanup
print("")
print("--- cleanup ---")
smoke_records = Lead.browse([i for i in created_ids if i]).exists()
smoke_records.write({"active": False})
still_active = smoke_records.filtered(lambda r: r.active)
check(
    "All %d smoke records archived (none deleted)" % len(smoke_records),
    not still_active,
    still_active.ids,
)

passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)

print("")
print("=" * 58)
if failed:
    print("FAILED CHECKS:")
    for name, ok, detail in results:
        if not ok:
            print("  - %s | %s" % (name, detail))
    print("")
print("SMOKE RESULT: %d passed, %d failed" % (passed, failed))
print("=" * 58)

env.cr.commit()
PYEOF

echo ""
if grep -qE "^SMOKE RESULT: [0-9]+ passed, 0 failed" "$LOG"; then
  echo "SMOKE TEST PASSED - every checked Odoo method behaved correctly on committed records."
  exit 0
fi
echo "SMOKE TEST FAILED - see the FAILED CHECKS block above." >&2
exit 1
