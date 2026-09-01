#!/bin/bash
# DEFECT 13, second diagnosis: capture the RAW HTTP response the live Odoo
# worker puts on the wire for ggd_prepare_draft.
#
# Usage:
#   ./scripts/diagnose-defect13-wire.sh
#
# Why this exists
# ---------------
# The first diagnosis (scripts/diagnose-json2-response.sh) reproduced Odoo's
# serializer inside `odoo shell` - a FRESH python process. That proved what the
# CURRENT source code would return. It could not prove what the LONG-RUNNING
# HTTP worker returns, because the worker imported its python at container
# start and Odoo does not re-import changed .py files on module upgrade. It
# also never looked at the actual bytes on the wire.
#
# This script closes both gaps. It talks to the live worker over real HTTP from
# inside the odoo container (same server, same code path n8n hits) and prints
# the status line, every response header, the declared Content-Length, the real
# byte count, and a repr of the body.
#
# Safety
# ------
# * Creates one throwaway lead under a unique name, archives it at the end.
# * Mints a temporary Odoo API key that expires in 1 hour and DELETES it in a
#   finally block. The key value is never printed and never leaves the process.
# * Never reads, prints or touches n8n credentials or .env.
# * Sends no email. Touches no Gate 3 fixture.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start Odoo first (docker compose up -d), then re-run." >&2
  exit 1
fi

echo ""
echo "STEP 0 - is the running worker's python older than the addon source?"
echo "===================================================================="
STARTED="$(docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q odoo)")"
echo "  odoo container started : $STARTED"
echo "  crm_lead.py modified   : $(date -u -r odoo/addons/ggd_crm/models/crm_lead.py '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || stat -c '%y' odoo/addons/ggd_crm/models/crm_lead.py)"
echo "  manifest version       : $(grep -o '19\.0\.[0-9.]*' odoo/addons/ggd_crm/__manifest__.py | head -1)"
echo ""
echo "  If the container started BEFORE crm_lead.py was modified, the live"
echo "  worker is still executing the OLD python. STEP 2 below settles it."
echo ""

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
import datetime
import http.client
import json
import os

DB = env.cr.dbname
KEYNAME = "GGD defect13 wire diagnostic (temporary, auto-deleted)"
LEADNAME = "[GGD-WIRE-DIAG] defect 13 wire capture (fictional)"

Lead = env["crm.lead"]
ApiKeys = env["res.users.apikeys"]

print("")
print("STEP 1 - throwaway lead")
print("=" * 70)
lead = Lead.with_context(active_test=False).search([("name", "=", LEADNAME)], limit=1)
if not lead:
    lead = Lead.create({
        "name": LEADNAME,
        "type": "opportunity",
        "email_from": "wirediag@ggd-wire-diag.invalid",
        "description": "Throwaway diagnostic lead. Fictional. Archived at end of run.",
    })
if not lead.active:
    lead.write({"active": True})
if lead.ggd_qualification_state != "ready":
    lead.ggd_apply_qualification(
        fit_score=70,
        summary="Wire diagnostic fixture: fictional supplier.",
        personalization_angle="Wire diagnostic angle: fictional export programme.",
        confidence=0.9,
        source_url="https://www.wire-diag.ggd-wire-diag.invalid/profil",
        industry="Diagnostics (fixture)",
        product_focus="Fixture focus.",
        recommended_buyer_roles=["Technical Buyer (fixture)"],
    )
lead.write({
    "ggd_draft_subject": False,
    "ggd_draft_body": False,
    "ggd_draft_version": False,
    "ggd_draft_status": "empty",
})
env.cr.commit()
print("  lead id = %s   draft_status = %s" % (lead.id, lead.ggd_draft_status))

env.cr.execute("SELECT user_id FROM res_users_apikeys ORDER BY id LIMIT 1")
row = env.cr.fetchone()
key_uid = row[0] if row else env.uid
print("  minting a temporary API key for user id %s (value never printed)" % key_uid)
expires = datetime.datetime.now() + datetime.timedelta(hours=1)
key = ApiKeys.with_user(key_uid)._generate("rpc", KEYNAME, expires)
env.cr.commit()


def call(label, path, payload, accept_encoding):
    print("")
    print("-" * 70)
    print("%s" % label)
    print("  POST %s" % path)
    print("  Accept-Encoding: %s" % accept_encoding)
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
        "Authorization": "Bearer %s" % key,
        "X-Odoo-Database": DB,
        "Accept-Encoding": accept_encoding,
    }
    conn = http.client.HTTPConnection("127.0.0.1", 8069, timeout=180)
    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        print("  <- HTTP %s %s" % (resp.status, resp.reason))
        for name, value in resp.getheaders():
            print("     %s: %s" % (name, value))
        declared = resp.getheader("Content-Length")
        print("  declared Content-Length : %s" % declared)
        print("  actual bytes received   : %s" % len(raw))
        if declared is not None and declared.isdigit() and int(declared) != len(raw):
            print("  *** MISMATCH: declared length differs from bytes received ***")
        if len(raw) == 0:
            print("  *** EMPTY BODY - this is what breaks n8n's JSON.parse ***")
        shown = raw if len(raw) <= 400 else raw[:200] + b" ... " + raw[-120:]
        print("  body repr: %r" % (shown,))
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            print("  *** json.loads FAILED: %s: %s ***" % (type(exc).__name__, exc))
        else:
            print("  json.loads OK -> %s" % type(parsed).__name__)
            if isinstance(parsed, dict):
                print("  keys: %s" % sorted(parsed)[:12])
            elif isinstance(parsed, list):
                print("  list length: %s" % len(parsed))
            else:
                print("  scalar value type %s  <-- NOT a JSON object" % type(parsed).__name__)
    finally:
        conn.close()


try:
    print("")
    print("STEP 2 - raw wire capture against the LIVE worker")
    print("=" * 70)
    print("Expected if the worker runs 19.0.1.7.0 : body is a JSON OBJECT")
    print("Expected if the worker runs stale code : body is a bare JSON STRING")
    call(
        "CONTROL - search_read (this is the node that already works)",
        "/json/2/crm.lead/search_read",
        {
            "domain": [["id", "=", lead.id]],
            "fields": ["id", "name", "email_from", "ggd_draft_status"],
            "limit": 1,
        },
        "gzip, deflate",
    )
    call(
        "SUBJECT - ggd_prepare_draft, ASCII subject/body, gzip accepted",
        "/json/2/crm.lead/ggd_prepare_draft",
        {
            "ids": [lead.id],
            "subject": "Diagnostic subject, ASCII only",
            "body": "Diagnostic body, ASCII only. Nothing is sent.",
        },
        "gzip, deflate",
    )
    call(
        "SUBJECT - ggd_prepare_draft, GERMAN subject/body, gzip accepted",
        "/json/2/crm.lead/ggd_prepare_draft",
        {
            "ids": [lead.id],
            "subject": "Diagnostik: Werkzeugbau Angebot fuer Gruenflaechen ÄÖÜäöüß",
            "body": "Sehr geehrte Damen und Herren,\n\ndies ist eine Diagnose. Umlaute: äöüß – Gedankenstrich, „Anführung“.\n\nMit freundlichen Grüßen",
        },
        "gzip, deflate",
    )
    call(
        "SUBJECT - ggd_prepare_draft, GERMAN subject/body, NO compression",
        "/json/2/crm.lead/ggd_prepare_draft",
        {
            "ids": [lead.id],
            "subject": "Diagnostik ohne Kompression ÄÖÜ",
            "body": "Diagnose ohne Kompression. Umlaute: äöüß",
        },
        "identity",
    )
finally:
    print("")
    print("STEP 3 - cleanup")
    print("=" * 70)
    stale = ApiKeys.sudo().search([("name", "=", KEYNAME)])
    if stale:
        ids = stale.ids
        stale.sudo()._remove()
        env.cr.commit()
        print("  temporary API key(s) deleted: %s" % ids)
    else:
        print("  no temporary API key found to delete")
    lead.write({"active": False})
    env.cr.commit()
    print("  diagnostic lead %s archived" % lead.id)
    print("")
PYEOF
