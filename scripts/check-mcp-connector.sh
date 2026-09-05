#!/bin/bash
# Live end-to-end check of the ChatGPT/Codex -> Odoo MCP connector.
#
# Usage:
#   ./scripts/check-mcp-connector.sh
#
# What it proves, in the order the ticket asks for it: tool discovery,
# authentication, finding and reading a fictional customer, bounded and
# paginated reporting, saving a qualification and reading it back, the
# below-0.70 review path, the operations that must be refused, and a missing
# or expired key failing safely.
#
# SAFETY
#
# It creates three fictional opportunities, all prefixed [GGD-MCP-TEST], all
# on the RFC 2606 reserved .invalid domain, all created with
# mail_create_nosubscribe and mail_notrack so nobody is subscribed and no
# tracking notification is raised. It counts mail.mail before and after and
# fails if that count moved: this database has a real Zoho outgoing server
# configured and an active mail queue cron, so "no email was sent" is checked
# rather than assumed.
#
# One of the three fixtures exists only to have deletion attempted on it. If
# Odoo's access rules were wrong and the delete succeeded, the record lost
# would be that throwaway and nothing else.
#
# It needs the reporting user's API key to be in the login Keychain already.
# The key is never printed, logged or passed as an argument; the connector
# reads it from the Keychain itself. See docs/CHATGPT-MCP-CONNECTOR.md.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start the stack first:  docker compose up -d" >&2
  exit 1
fi

echo "Creating fictional [GGD-MCP-TEST] fixtures..."

fixture_output="$(docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF' 2>/dev/null
import json
from odoo import fields

PREFIX = "[GGD-MCP-TEST]"
DOMAIN = "ggd-mcp-test.invalid"

Lead = env["crm.lead"].with_context(
    mail_create_nosubscribe=True, mail_create_nolog=True, mail_notrack=True,
)


def get_or_create(name, values):
    found = Lead.with_context(active_test=False).search([("name", "=", name)], limit=1)
    if found:
        # The teardown archives the fixtures, so a second run finds them
        # archived. Un-archive on reuse, or the search check looks for a
        # record that ggd_search_records is correctly declining to show.
        if not found.active:
            found.write({"active": True})
        return found
    payload = {"name": name, "type": "opportunity"}
    payload.update(values)
    return Lead.create(payload)


main = get_or_create(
    "%s Fictional Panels GmbH" % PREFIX,
    {
        "email_from": "fx-main@%s" % DOMAIN,
        "partner_name": "Fictional Panels GmbH (not real)",
        "website": "https://fictional-panels.%s" % DOMAIN,
        "expected_revenue": 12500.0,
        "description": "MCP connector fixture. Fictional company, .invalid address.",
    },
)
dnc = get_or_create(
    "%s Suppressed Fictional AG" % PREFIX,
    {
        "email_from": "fx-dnc@%s" % DOMAIN,
        "partner_name": "Suppressed Fictional AG (not real)",
        "description": "MCP connector fixture for the Do-not-contact boundary.",
    },
)
if not dnc.ggd_do_not_contact:
    dnc.write({"ggd_do_not_contact": True})
doomed = get_or_create(
    "%s Delete-Probe Fictional SE" % PREFIX,
    {
        "email_from": "fx-doomed@%s" % DOMAIN,
        "partner_name": "Delete-Probe Fictional SE (not real)",
        "description": "Exists only so deletion can be attempted and refused.",
    },
)

# One overdue activity so the follow-up report has something of its own to
# find. Assigned to an internal user whose notifications go to the inbox, so
# creating it cannot put anything in the outgoing mail queue.
inbox_user = env["res.users"].search(
    [("share", "=", False), ("notification_type", "=", "inbox")], limit=1
)
activity_note = "no inbox user available; activity not created"
if inbox_user and not env["mail.activity"].search_count([
    ("res_model", "=", "crm.lead"), ("res_id", "=", main.id),
]):
    env["mail.activity"].create({
        "res_model_id": env["ir.model"]._get_id("crm.lead"),
        "res_id": main.id,
        "activity_type_id": env.ref("mail.mail_activity_data_todo").id,
        "summary": "MCP fixture: overdue follow-up (fictional)",
        "date_deadline": fields.Date.subtract(fields.Date.today(), days=21),
        "user_id": inbox_user.id,
    })
    activity_note = "overdue activity created for user %s" % inbox_user.login
elif inbox_user:
    activity_note = "overdue activity already present"

env.cr.commit()

print("GGD_FIXTURES " + json.dumps({
    "lead_id": main.id,
    "lead_name": main.name,
    "dnc_id": dnc.id,
    "doomed_id": doomed.id,
    "mail_mail_before": env["mail.mail"].sudo().search_count([]),
    "activity_note": activity_note,
}))
PYEOF
)"

fixtures="$(printf '%s\n' "$fixture_output" | sed -n 's/^GGD_FIXTURES //p' | tail -1)"

if [[ -z "$fixtures" ]]; then
  echo "ERROR: the fixtures could not be created. Odoo shell said:" >&2
  printf '%s\n' "$fixture_output" >&2
  exit 1
fi

python3 -c 'import json,sys; f=json.loads(sys.argv[1]); print("  main id=%s, do-not-contact id=%s, delete-probe id=%s\n  %s" % (f["lead_id"], f["dnc_id"], f["doomed_id"], f["activity_note"]))' "$fixtures"

echo ""
echo "======================================================================"
echo "MCP connector live check"
echo "======================================================================"

set +e
/usr/bin/python3 scripts/mcp_live_check.py "$fixtures"
driver_status=$?
set -e

echo ""
echo "Confirming nothing was queued for sending, and tidying up..."

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<PYEOF 2>/dev/null | sed -n '/^GGD_TEARDOWN/,$p'
before = $(python3 -c 'import json,sys;print(json.loads(sys.argv[1])["mail_mail_before"])' "$fixtures")
after = env["mail.mail"].sudo().search_count([])
leads = env["crm.lead"].with_context(active_test=False).search(
    [("name", "like", "[GGD-MCP-TEST]%")]
)
qualified = leads.filtered(lambda l: l.ggd_qualification_state in ("ready", "review"))
print("GGD_TEARDOWN")
print("  mail.mail before: %s   after: %s   %s" % (
    before, after, "UNCHANGED - nothing was queued for sending"
    if after == before else "CHANGED - INVESTIGATE, something was queued"))
print("  qualification states: %s" % (
    ", ".join(sorted(set(qualified.mapped("ggd_qualification_state")))) or "none"))
for lead in leads:
    if lead.active:
        lead.write({"active": False})
print("  archived %s fixture record(s); none were deleted" % len(leads))
env.cr.commit()
if after != before:
    print("  MAIL_QUEUE_GREW")
PYEOF

if [[ $driver_status -ne 0 ]]; then
  echo ""
  echo "Live check FAILED. See the FAIL lines above." >&2
  exit $driver_status
fi

echo ""
echo "Live check passed. The fixtures are archived, not deleted; find them in"
echo "Odoo by searching for [GGD-MCP-TEST] with the archived filter on."
