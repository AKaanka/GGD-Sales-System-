#!/bin/bash
# Read-only check of WHO the automation key authenticates as (never the key).
#
# Usage:
#   ./scripts/check-odoo-automation-user.sh
#
# Why this exists (finding S3, ticket #7): the JSON-2 endpoint exposes every
# public method on crm.lead, so the only boundary between "n8n is compromised"
# and "the CRM is compromised" is the access rights of the user the API key
# belongs to. If that user is the administrator, the Outreach approver group
# protects nothing: a Settings user can add itself to the group, and the
# superuser is exempt from every access rule in Odoo.
#
# This script prints, for every API key: the key id and name, the LOGIN of the
# user it belongs to, that user's relevant group memberships, and a verdict.
# The key value itself is stored hashed and is unreadable by design - Odoo
# shows it exactly once, at creation. Nothing secret is read or printed here,
# so the output is safe to paste into the ticket.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start the stack first:  docker compose up -d" >&2
  exit 1
fi

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
APPROVER = "ggd_crm.group_ggd_outreach_approver"

# (xmlid, short label) - the memberships that decide the verdict.
CHECKS = [
    ("base.group_user", "internal user"),
    ("sales_team.group_sale_salesman", "CRM: user"),
    ("sales_team.group_sale_salesman_all_leads", "CRM: all documents"),
    ("sales_team.group_sale_manager", "CRM: administrator"),
    ("base.group_system", "SETTINGS / administration"),
    (APPROVER, "Outreach approver"),
]


def in_group(user, xmlid):
    """True/False, or None when the group does not exist in this database."""
    try:
        return user.has_group(xmlid)
    except Exception:
        return None


Keys = env["res.users.apikeys"].sudo()
rows = Keys.search([])

print("")
print("Odoo API keys - OWNER AND PRIVILEGES ONLY (no key value is readable)")
print("=" * 74)

if not rows:
    print("")
    print("  NO API KEYS EXIST AT ALL.")
    print("  Run ./scripts/check-odoo-api-keys.sh for the expiry explanation.")
    print("")
else:
    problems = 0
    for k in rows:
        user = k.user_id.sudo()
        memberships = [(label, in_group(user, xmlid)) for xmlid, label in CHECKS]
        held = [label for label, yes in memberships if yes]
        missing_groups = [label for label, yes in memberships if yes is None]

        is_superuser = user.id == 1
        is_settings = in_group(user, "base.group_system") is True
        is_approver = in_group(user, APPROVER) is True
        is_internal = in_group(user, "base.group_user") is True
        has_crm = any(
            in_group(user, x) is True
            for x in (
                "sales_team.group_sale_salesman",
                "sales_team.group_sale_salesman_all_leads",
                "sales_team.group_sale_manager",
            )
        )

        faults = []
        if is_superuser:
            faults.append("owner is the SUPERUSER - exempt from every access rule")
        if is_settings:
            faults.append("owner has Settings/administration rights")
        if is_approver:
            faults.append("owner is in Outreach approver - it could approve its own outreach")
        if user.share:
            faults.append("owner is a portal/public user, not an internal user")
        if not is_internal:
            faults.append("owner is not an internal user")
        if not has_crm:
            faults.append("owner has no CRM access - the workflows cannot read leads")

        print("")
        print("  key id %s  name %r" % (k.id, (k.name or "-")))
        print("    owner login : %s" % (user.login or "-"))
        print("    owner name  : %s" % (user.name or "-"))
        print("    scope       : %s" % (k.scope or "rpc"))
        print("    groups      : %s" % (", ".join(held) or "(none of the checked groups)"))
        if missing_groups:
            print("    not checked : %s (group not installed)" % ", ".join(missing_groups))
        if faults:
            problems += 1
            print("    VERDICT     : FAIL")
            for f in faults:
                print("                  - %s" % f)
        else:
            print("    VERDICT     : PASS - dedicated internal CRM user, not an approver")

    print("")
    print("=" * 74)
    if problems:
        print("%d of %d key(s) FAIL finding S3." % (problems, len(rows)))
        print("Fix: create a dedicated internal user with CRM access only, issue")
        print("its key, swap the n8n credential, verify the six workflows, then")
        print("delete the failing key. See docs/ODOO-SETUP.md, 'Automation")
        print("service user'. Kaan does the key handling; no agent sees a value.")
    else:
        print("All %d key(s) satisfy finding S3." % len(rows))

print("=" * 74)
print("")
PYEOF
