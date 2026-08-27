#!/bin/bash
# Create one throwaway qualified-ready lead with NO draft, so Workflow 2 has
# something to select when re-testing the defect 13 fix.
#
# Usage:
#   ./scripts/make-workflow2-retest-lead.sh            # create (idempotent)
#   ./scripts/make-workflow2-retest-lead.sh --archive  # archive it when done
#
# Why not just re-run Workflow 2 against FX2?
#   FX2 (431) already carries a stored draft plus the recorded reply from Gate
#   3 step 4 scenario 1. Clearing its draft to free it for another run would
#   destroy passing Gate 3 evidence and replace the exact draft Kaan is
#   supposed to read without approving. Evidence is not scratch space, so this
#   makes a separate record instead.
#
# Workflow 2's selector requires, per its own domain:
#   active=true, ggd_qualification_state='ready', ggd_automation_needs_review=false,
#   ggd_do_not_contact=false, ggd_outreach_approved=false,
#   ggd_draft_status='empty', email_from!=false
# This lead satisfies exactly that and nothing more.
#
# Fictional .invalid address. Sends no email. Touches no Gate 3 fixture.

set -euo pipefail

cd "$(dirname "$0")/.."

MODE="create"
if [[ "${1:-}" == "--archive" ]]; then
  MODE="archive"
fi

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start Odoo first (docker compose up -d), then re-run." >&2
  exit 1
fi

docker compose exec -T -e GGD_MODE="$MODE" odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
import os

Lead = env["crm.lead"]
NAME = "[GGD-W2-RETEST] Defect 13 re-test (Weser Fictional Werkzeugbau GmbH)"
mode = os.environ.get("GGD_MODE", "create")

existing = Lead.with_context(active_test=False).search([("name", "=", NAME)], limit=1)

if mode == "archive":
    if existing:
        existing.write({"active": False})
        env.cr.commit()
        print("ARCHIVED  id=%s" % existing.id)
    else:
        print("Nothing to archive.")
else:
    if existing and existing.active and existing.ggd_draft_status == "empty":
        print("EXISTS    id=%s  already selectable by Workflow 2" % existing.id)
        lead = existing
    elif existing and existing.ggd_draft_status in ("ready", "empty"):
        # A previous run stored a draft on this throwaway lead, so Workflow 2's
        # selector (ggd_draft_status = 'empty') no longer matches it. Clear it
        # back to selectable in TWO writes, on purpose:
        #   1. Clearing the draft fields counts as a draft change, and write()
        #      forces ggd_draft_status = 'ready' for any draft change. That is
        #      correct for an edit and wrong for a clear, so the first write
        #      alone would leave status='ready' with no version.
        #   2. A second write that touches ONLY the status is not a draft
        #      change, so it is left alone and the reset actually sticks.
        # Only ever run against this throwaway lead; never against a fixture.
        lead = existing
        if not lead.active:
            lead.write({"active": True})
        lead.write({
            "ggd_draft_subject": False,
            "ggd_draft_body": False,
            "ggd_draft_version": False,
        })
        lead.write({"ggd_draft_status": "empty"})
        env.cr.commit()
        print("RESET     id=%s  previous draft cleared, selectable again" % lead.id)
    else:
        lead = existing or Lead.create({
            "name": NAME,
            "type": "opportunity",
            "email_from": "w2retest@ggd-w2-retest.invalid",
            "description": (
                "Throwaway lead for re-testing Workflow 2 after the defect 13 "
                "fix. Fictional. Archive with --archive when done."
            ),
        })
        if not lead.active:
            lead.write({"active": True})
        if lead.ggd_qualification_state != "ready":
            lead.ggd_apply_qualification(
                fit_score=72,
                summary="Re-test fixture: fictional toolmaking supplier, plausible fit.",
                personalization_angle="Re-test angle: fictional new export programme.",
                confidence=0.88,
                source_url="https://www.weser-fictional.ggd-w2-retest.invalid/profil",
                industry="Toolmaking (re-test fixture)",
                product_focus="Re-test focus: precision jigs.",
                recommended_buyer_roles=["Technical Buyer (fixture)"],
            )
        env.cr.commit()
        print("READY     id=%s" % lead.id)

    print("")
    print("  qualification_state = %s" % lead.ggd_qualification_state)
    print("  draft_status        = %s" % lead.ggd_draft_status)
    print("  outreach_approved   = %s" % lead.ggd_outreach_approved)
    print("  needs_review        = %s" % lead.ggd_automation_needs_review)
    print("")
    print("Workflow 2 should now select this lead. After running it, expect:")
    print("  draft_status -> ready, a subject and version stored,")
    print("  outreach_approved still False, and the n8n node GREEN.")
PYEOF
