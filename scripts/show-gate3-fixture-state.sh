#!/bin/bash
# Read-only state dump of the Gate 3 fixtures (FX1-FX7, Odoo ids 430-437).
#
# Usage:
#   ./scripts/show-gate3-fixture-state.sh
#
# Run it BEFORE and AFTER each Gate 3 workflow step. Comparing the two tells
# you exactly what the workflow changed, without clicking through the Odoo UI
# and without trusting the n8n execution log's own account of itself.
#
# This script only reads. It never writes, never commits, never sends email,
# and never touches n8n. It is safe to run at any time, including while a
# workflow is executing.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start Odoo first (docker compose up -d), then re-run." >&2
  exit 1
fi

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
Lead = env["crm.lead"]
Activity = env["mail.activity"]

leads = Lead.with_context(active_test=False).search(
    [("name", "like", "[GGD-GATE3-FIXTURE]%")], order="id asc"
)


def short(value, width=34):
    if value is False or value is None or value == "":
        return "-"
    text = str(value).replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def yn(value):
    return "YES" if value else "no"


print("")
print("Gate 3 fixture state  (read-only)")
print("=" * 72)

if not leads:
    print("  No [GGD-GATE3-FIXTURE] records found. Run ./scripts/create-gate3-fixtures.sh")

for lead in leads:
    tag = lead.name.replace("[GGD-GATE3-FIXTURE] ", "").split(" (")[0]
    acts = Activity.search_count(
        [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)]
    )
    msgs = len(lead.message_ids)
    print("")
    print("  id=%-4s %s" % (lead.id, tag))
    print("    active=%-4s stage=%-22s activities=%-3s chatter=%s"
          % (yn(lead.active), short(lead.stage_id.display_name, 22), acts, msgs))
    print("    QUALIFY   state=%-8s fit=%-4s conf=%-5s"
          % (lead.ggd_qualification_state or "-",
             lead.ggd_fit_score,
             lead.ggd_ai_confidence))
    print("              industry=%s" % short(lead.ggd_industry))
    print("    DRAFT     status=%-9s version=%-10s subject=%s"
          % (lead.ggd_draft_status or "-",
             short(lead.ggd_draft_version, 10),
             short(lead.ggd_draft_subject, 30)))
    print("    APPROVAL  approved=%-4s by=%-14s approved_version=%s"
          % (yn(lead.ggd_outreach_approved),
             short(lead.ggd_outreach_approved_by.display_name, 14),
             short(lead.ggd_approved_draft_version, 10)))
    print("              basis=%-16s do_not_contact=%s"
          % (lead.ggd_contact_basis or "-", yn(lead.ggd_do_not_contact)))
    print("    SEND      delivery=%-9s confirmed_at=%-20s"
          % (lead.ggd_delivery_status or "-", short(lead.ggd_send_confirmed_at, 20)))
    print("              send_key=%-16s message_id=%s"
          % (short(lead.ggd_last_send_key, 16), short(lead.ggd_last_message_id, 30)))
    print("    REPLY     category=%-14s received=%-20s"
          % (lead.ggd_reply_category or "-", short(lead.ggd_last_reply_received_at, 20)))
    print("              summary=%s" % short(lead.ggd_reply_summary, 40))
    print("    FOLLOWUP  queue_key=%-20s queued_at=%s"
          % (short(lead.ggd_last_follow_up_queue_key, 20),
             short(lead.ggd_last_follow_up_queued_at, 20)))
    print("    REVIEW    any=%-4s qual=%-4s reply=%-4s deliv=%-4s wf=%s"
          % (yn(lead.ggd_automation_needs_review),
             yn(lead.ggd_qualification_needs_review),
             yn(lead.ggd_reply_needs_review),
             yn(lead.ggd_delivery_needs_review),
             yn(lead.ggd_workflow_needs_review)))
    if lead.ggd_automation_review_summary:
        print("              %s" % short(lead.ggd_automation_review_summary, 56))

# Anything Workflow 4 created outside the fixture set.
inbound = Lead.with_context(active_test=False).search(
    [("name", "like", "Manual inbound review:%")], order="id asc"
)
print("")
print("=" * 72)
print("  Unmatched-inbound review records created by Workflow 4: %d" % len(inbound))
for rec in inbound:
    print("    id=%-4s %s  review=%s" % (rec.id, short(rec.name, 44), yn(rec.ggd_automation_needs_review)))
print("=" * 72)
print("")
PYEOF
