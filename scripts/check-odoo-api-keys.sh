#!/bin/bash
# Read-only check of Odoo API key METADATA (never the key itself).
#
# Usage:
#   ./scripts/check-odoo-api-keys.sh
#
# Why this exists: Workflow 2 failed on 27 August with
#   401 Unauthorized: Invalid apikey
# on its very first node, after having worked the previous evening.
#
# In Odoo 19, res.users.apikeys carries an `expiration_date`, and
# _check_apikey_credentials only accepts a key where
#   expiration_date IS NULL OR expiration_date >= now()
# (odoo/addons/base/models/res_users.py, ~line 1700). An @api.autovacuum
# then DELETES keys whose expiration_date has passed, so an expired key
# stops working and then disappears entirely.
#
# SECURITY: this prints only id, name, user, scope, created and expiry. The
# key value itself is stored as a hash (the model uses _auto = False with a
# secret column) and is unreadable by design - Odoo shows it exactly once, at
# creation. Nothing secret is read, printed, exported or copied here.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  exit 1
fi

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
from odoo import fields

Keys = env["res.users.apikeys"].sudo()
now = fields.Datetime.now()

rows = Keys.search([])

print("")
print("Odoo API keys - METADATA ONLY (no key value is readable, by design)")
print("=" * 74)
print("Server time now: %s UTC" % now)
print("")

if not rows:
    print("  NO API KEYS EXIST AT ALL.")
    print("")
    print("  This is consistent with an expired key: Odoo's autovacuum deletes")
    print("  keys whose expiration_date has passed, so an expired key first")
    print("  stops authenticating and is then removed entirely.")
else:
    print("  %-5s %-26s %-18s %-8s %-20s %s" % ("id", "name", "user", "scope", "expires", "state"))
    print("  " + "-" * 70)
    for k in rows:
        exp = k.expiration_date
        if not exp:
            state = "OK (never expires)"
            exp_s = "never"
        elif exp < now:
            state = "EXPIRED"
            exp_s = str(exp)
        else:
            state = "OK (valid)"
            exp_s = str(exp)
        print("  %-5s %-26s %-18s %-8s %-20s %s" % (
            k.id,
            (k.name or "-")[:26],
            (k.user_id.login or "-")[:18],
            (k.scope or "rpc")[:8],
            exp_s,
            state,
        ))

print("")
print("=" * 74)
print("If no valid 'rpc' key exists for the automation user, the n8n")
print("'Header Auth account' credential is pointing at a key Odoo no longer")
print("accepts. Fix: create a NEW key with expiry 'Never', then paste it into")
print("that n8n credential as: Bearer <newkey>")
print("Kaan does this; no agent should ever see the value.")
print("=" * 74)
print("")
PYEOF
