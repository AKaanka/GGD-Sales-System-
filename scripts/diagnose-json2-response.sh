#!/bin/bash
# Diagnose DEFECT 13: Workflow 2's "Store immutable draft for human approval"
# node reports "Response body is not valid JSON" even though Odoo performed the
# work and committed it.
#
# Usage:
#   ./scripts/diagnose-json2-response.sh
#
# What it does: reproduces exactly what Odoo's JSON-2 endpoint would put on the
# wire for each addon method the workflows call, using Odoo's own serializer
# (odoo.http.make_json_response does `json.dumps(data, ensure_ascii=False,
# default=json_default)` and then sets Content-Length to len(data) IN
# CHARACTERS, addons/../odoo/http.py:2084-2087). If any response's character
# count differs from its UTF-8 byte count, Content-Length is short and the
# client receives a truncated body — which reads exactly like "not valid JSON".
#
# It creates one throwaway lead, exercises the return values, archives it, and
# rolls back. It writes nothing durable, sends no email, and does not touch the
# Gate 3 fixtures.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  exit 1
fi

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
import json
from odoo.http import json_default

Lead = env["crm.lead"]

NOTE = ("Diagnostic evidence only (not real): simulated opt-in, ref DIAG-13.")


def wire(label, value):
    """Exactly what odoo.http.make_json_response would send."""
    body = json.dumps(value, ensure_ascii=False, default=json_default)
    chars = len(body)
    data = body.encode("utf-8")
    nbytes = len(data)
    ok = "OK " if chars == nbytes else "MISMATCH"
    shown = body if len(body) <= 70 else body[:67] + "..."
    print("  %-8s %-34s Content-Length=%-5s actual_bytes=%-5s  %s"
          % (ok, label, chars, nbytes, shown))
    return chars == nbytes


print("")
print("DEFECT 13 diagnostic - Odoo JSON-2 response bodies")
print("=" * 78)
print("Odoo sets Content-Length = len(json_string) in CHARACTERS (http.py:2087).")
print("Any non-ASCII in a response makes Content-Length shorter than the real")
print("UTF-8 byte length, so the client reads a truncated, unparseable body.")
print("")

lead = Lead.create({
    "name": "[GGD-DIAG-13] throwaway",
    "type": "opportunity",
    "email_from": "diag13@ggd-diagnostic.invalid",
    "description": "Diagnostic throwaway. Archived and rolled back.",
})

print("Return values of the methods the workflows call:")
results = {}

version = lead.ggd_prepare_draft("Diag subject", "Diag body, never mailed.")
results["ggd_prepare_draft"] = wire("ggd_prepare_draft (dict)", version)

lead.write({"ggd_contact_basis": "consent", "ggd_contact_basis_note": NOTE})
lead.action_ggd_approve_outreach()
claimed = lead.ggd_claim_send_key("%s:%s" % (lead.id, lead.ggd_approved_draft_version))
results["ggd_claim_send_key"] = wire("ggd_claim_send_key (bool)", claimed)

finalized = lead.ggd_finalize_send(
    "<diag13@ggd-diagnostic.invalid>",
    lead.ggd_approved_recipient,
    lead.ggd_draft_subject,
    "Diag summary.",
)
results["ggd_finalize_send"] = wire("ggd_finalize_send (bool)", finalized)

match = Lead.ggd_find_reply_candidates(in_reply_to="<diag13@ggd-diagnostic.invalid>")
results["ggd_find_reply_candidates"] = wire("ggd_find_reply_candidates (dict)", match)

print("")
print("The same serialization applied to this addon's ERROR messages:")
print("(these travel through Dispatcher.handle_error -> make_json_response too)")

samples = {
    "UWG s7 refusal (contains non-ASCII)": (
        "Contact basis 'Referral / introduction (do not email)' is not a lawful "
        "basis for a first marketing email under UWG §7. Outreach cannot be "
        "approved. Use a telephone call, a warm introduction, or post instead — "
        "or record the opt-in evidence and change the basis."
    ),
    "plain ASCII refusal": (
        "A valid recipient email address is required before approval."
    ),
}
for label, text in samples.items():
    wire(label, {"message": text})

print("")
print("=" * 78)
bad = [name for name, ok in results.items() if not ok]
if bad:
    print("METHOD RETURN VALUES WITH A CONTENT-LENGTH MISMATCH: %s" % ", ".join(bad))
else:
    print("All method RETURN VALUES are pure ASCII: Content-Length is correct for")
    print("them, so truncation does NOT explain the Workflow 2 failure.")
    print("")
    print("=> The remaining explanation is client-side: n8n's HTTP Request node")
    print("   rejects a bare top-level JSON scalar STRING (ggd_prepare_draft is")
    print("   the only workflow-called method returning one; every other method")
    print("   returns a bool, int, dict or list, and those all parse fine -")
    print("   Workflow 5's node returned bare `false` without complaint).")
print("=" * 78)
print("")

lead.write({"active": False})
env.cr.rollback()
print("Diagnostic rolled back. No durable record was created.")
PYEOF
