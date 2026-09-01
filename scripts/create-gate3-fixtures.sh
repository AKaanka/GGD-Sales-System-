#!/bin/bash
# Create the fictional .invalid fixtures Gate 3 (docs/FOUR-AGENT-EXECUTION-PLAN.md)
# needs for non-send functional testing of Workflows 1, 2, 4, and 5, plus one
# already-approved-draft record reserved for the Gate 4 controlled-send test.
#
# Usage:
#   ./scripts/create-gate3-fixtures.sh
#
# Idempotent: every fixture is looked up by its exact fixture name before
# creation. Re-running this script updates nothing and creates nothing if the
# fixtures already exist -- it only reports the existing IDs.
#
# Scope: creates records through odoo/addons/ggd_crm's own model methods
# (ggd_apply_qualification, ggd_prepare_draft, action_ggd_approve_outreach,
# and for FX5/FX7 also ggd_claim_send_key / ggd_finalize_send), the same
# public API Workflows 1-3 use, so the fixtures reach states the addon
# itself considers valid rather than states hand-written to look similar.
#
# All records use fictional company names and a fictional .invalid email
# domain (RFC 2606 reserved test TLD). Nothing here sends email, activates
# an n8n workflow, or touches real prospect data. Neither ggd_claim_send_key
# nor ggd_finalize_send calls SMTP -- that only happens in n8n's SMTP node,
# outside Odoo -- so FX5/FX7 reaching an "already sent" state below never
# sends an email either.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose exec -T odoo /bin/bash -lc '[ -r /tmp/ggd-odoo.conf ]' >/dev/null 2>&1; then
  echo "ERROR: cannot read /tmp/ggd-odoo.conf inside the odoo container." >&2
  echo "Start the normal Odoo service first (docker compose up -d), then re-run this script." >&2
  exit 1
fi

echo "Creating/verifying Gate 3 fixtures in the ggd database..."
echo "========================================"

docker compose exec -T odoo /bin/bash -lc '
  exec odoo shell --config=/tmp/ggd-odoo.conf -d "$ODOO_DB_NAME" --no-http
' <<'PYEOF'
from datetime import datetime, timedelta

Lead = env['crm.lead']
Stage = env['crm.stage']

FIXTURE_PREFIX = "[GGD-GATE3-FIXTURE]"
DOMAIN = "ggd-gate3-fixture.invalid"
VALID_BASIS_NOTE = (
    "Fixture evidence only (not real): simulated opt-in via GGD website "
    "contact form, dated 2026-08-01, reference GATE3-SIM-001."
)

created = []
existing = []


def stage(name):
    """Best-effort lookup of a pipeline stage created per docs/ODOO-SETUP.md.
    Returns an empty recordset (not an error) if Kaan has not created the
    stage yet, so the fixture script never fails on stage setup order."""
    return Stage.search([("name", "=", name)], limit=1)


def get_or_create(fixture_key, name, values):
    """Idempotent create keyed on the exact fixture name.

    Returns (lead, was_created). Existing records are left untouched -- this
    script only fills in gaps, it never overwrites fixture data a human may
    have since edited by hand while testing.
    """
    found = Lead.with_context(active_test=False).search([("name", "=", name)], limit=1)
    if found:
        existing.append((fixture_key, found.id, name))
        return found, False
    lead = Lead.create(values)
    created.append((fixture_key, lead.id, name))
    return lead, True


# ---------------------------------------------------------------------------
# FX1 -- pending qualification, with a fictional research source URL.
# Exercises Workflow 1 (lead qualification) starting from Odoo's default
# ggd_qualification_state = "pending".
# ---------------------------------------------------------------------------
fx1_name = f"{FIXTURE_PREFIX} FX1 -- Pending Qualification (Nordlicht Fictional GmbH)"
fx1, fx1_new = get_or_create(
    "FX1_PENDING",
    fx1_name,
    {
        "name": fx1_name,
        "type": "opportunity",
        "email_from": f"fx1@{DOMAIN}",
        "ggd_source_url": f"https://www.nordlicht-fictional.{DOMAIN}/ueber-uns",
        "description": (
            "Gate 3 fixture. Fictional company, fictional URL, .invalid "
            "address. Left at the default pending qualification state for "
            "Workflow 1 testing."
        ),
        "stage_id": stage("Target Identified").id or False,
    },
)

# ---------------------------------------------------------------------------
# FX2 -- qualification already applied and marked ready, no draft yet.
# Exercises Workflow 2 (draft and approval queue), which expects a
# qualified-ready lead to draft against.
# ---------------------------------------------------------------------------
fx2_name = f"{FIXTURE_PREFIX} FX2 -- Qualified, Ready to Draft (Baltic Gears Fictional AG)"
fx2, fx2_new = get_or_create(
    "FX2_QUALIFIED_READY",
    fx2_name,
    {
        "name": fx2_name,
        "type": "opportunity",
        "email_from": f"fx2@{DOMAIN}",
        "description": "Gate 3 fixture. Fictional company, .invalid address.",
        "stage_id": stage("Qualified").id or False,
    },
)
if fx2.ggd_qualification_state != "ready":
    fx2.ggd_apply_qualification(
        fit_score=74,
        summary="Fixture fit assessment: mid-size fictional machinery distributor, plausible fit.",
        personalization_angle="Fixture angle: recent fictional trade-fair presence in Hannover.",
        confidence=0.86,
        source_url=f"https://www.balticgears-fictional.{DOMAIN}/produkte",
        industry="Industrial machinery (fixture)",
        product_focus="Fixture product focus: packaging line components.",
        recommended_buyer_roles=["Head of Procurement (fixture)"],
    )

# ---------------------------------------------------------------------------
# FX3 -- Do Not Contact, for the suppression-gate tests in Workflows 2-5.
# ---------------------------------------------------------------------------
fx3_name = f"{FIXTURE_PREFIX} FX3 -- Do Not Contact (Rhein Fictional Handels UG)"
fx3, fx3_new = get_or_create(
    "FX3_DO_NOT_CONTACT",
    fx3_name,
    {
        "name": fx3_name,
        "type": "opportunity",
        "email_from": f"fx3@{DOMAIN}",
        "ggd_do_not_contact": True,
        "description": (
            "Gate 3 fixture. Fictional company. Do Not Contact is set from "
            "creation to exercise the suppression gate; every outbound "
            "workflow must refuse this record."
        ),
        "stage_id": stage("Do Not Contact").id or False,
    },
)

# ---------------------------------------------------------------------------
# FX4 -- qualified, drafted, and approved. Reserved for the Gate 4 controlled
# send test later. IMPORTANT: this uses a .invalid recipient, which Gate 4
# explicitly forbids for a real send (Kaan must own the recipient address).
# Before Gate 4 runs, email_from must be changed to a real Kaan-owned test
# address and outreach re-approved -- changing email_from on an approved
# record automatically revokes the old approval (see write() in
# odoo/addons/ggd_crm/models/crm_lead.py), so this is a safe placeholder,
# not a live send target.
# ---------------------------------------------------------------------------
fx4_name = f"{FIXTURE_PREFIX} FX4 -- Approved Draft, Reserved for Gate 4 (Schwarzwald Fictional Maschinenbau KG)"
fx4, fx4_new = get_or_create(
    "FX4_APPROVED_DRAFT",
    fx4_name,
    {
        "name": fx4_name,
        "type": "opportunity",
        "email_from": f"fx4@{DOMAIN}",
        "description": (
            "Gate 3 fixture, reserved for Gate 4. RECIPIENT IS FICTIONAL "
            "(.invalid) -- replace email_from with a Kaan-owned test address "
            "and re-run outreach approval before any real Workflow 3 test."
        ),
        "stage_id": stage("Waiting for Approval").id or False,
    },
)
if fx4.ggd_qualification_state != "ready":
    fx4.ggd_apply_qualification(
        fit_score=81,
        summary="Fixture fit assessment: fictional precision-machinery manufacturer, strong fit.",
        personalization_angle="Fixture angle: fictional expansion into the Turkish market noted on their site.",
        confidence=0.9,
        source_url=f"https://www.schwarzwald-fictional.{DOMAIN}/unternehmen",
        industry="Precision machinery (fixture)",
        product_focus="Fixture product focus: CNC tooling components.",
        recommended_buyer_roles=["Managing Director (fixture)"],
    )
if not fx4.ggd_outreach_approved:
    fx4.ggd_prepare_draft(
        subject="Fixture subject: Introduction from Germany Growth Desk (Gate 3 test)",
        body=(
            "Fixture body -- not a real outreach email.\n\n"
            "This draft exists only to prove the stored-draft and approval "
            "path for Gate 3 / Gate 4 testing. It must never be sent to "
            "this .invalid address."
        ),
    )
    fx4.write(
        {
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_BASIS_NOTE,
        }
    )
    fx4.action_ggd_approve_outreach()

# ---------------------------------------------------------------------------
# FX5 -- reaches an "already sent" state through the addon's own real send
# path: ggd_claim_send_key() then ggd_finalize_send(). This fixture is for
# Workflow 4's message-ID reply match and for ggd_record_bounce(), both of
# which require a record that has actually gone through this path.
#
# An earlier version of this script hand-wrote the sent-state fields
# instead, and an orchestrator review found two defects in that approach:
#   1. A hand-picked send key does not match the addon's required shape
#      (opportunity id + ":" + approved draft version, enforced by
#      _ggd_check_send_key_matches_approved_draft) -- any write carrying a
#      key in the wrong shape is rejected.
#   2. write()'s suppression-wins guard drops ggd_last_send_key from any
#      single write that also revokes approval, so "sent AND approval
#      revoked" cannot be produced in one write -- it needs two.
#      ggd_finalize_send() already does this correctly across its own two
#      writes (its own write() call does not carry ggd_last_send_key at
#      all, so the key-drop guard never fires for it), which is exactly the
#      two-write shape the review asked for -- via the addon's own tested
#      method instead of a hand-rolled third write.
# ---------------------------------------------------------------------------
fx5_name = f"{FIXTURE_PREFIX} FX5 -- Synthetic Already-Sent, For Reply/Bounce Match Tests (Alpen Fictional Logistik SE)"
fx5, fx5_new = get_or_create(
    "FX5_SENT_SYNTHETIC",
    fx5_name,
    {
        "name": fx5_name,
        "type": "opportunity",
        "email_from": f"fx5@{DOMAIN}",
        "description": (
            "Gate 3 fixture. Reached its already-sent state via the real "
            "ggd_claim_send_key/ggd_finalize_send methods, called directly "
            "from this script -- neither method calls SMTP, so no email "
            "was ever sent for this record."
        ),
        "stage_id": stage("Contacted").id or False,
    },
)
FX5_MESSAGE_ID = f"<gate3-fixture-fx5-001@{DOMAIN}>"
FX5_SEND_KEY = fx5.ggd_last_confirmed_send_key or None
if not fx5.ggd_send_confirmed_at:
    if fx5.ggd_qualification_state != "ready":
        fx5.ggd_apply_qualification(
            fit_score=68,
            summary="Fixture fit assessment: fictional logistics provider.",
            personalization_angle="Fixture angle: fictional cross-border shipping lanes.",
            confidence=0.75,
            source_url=f"https://www.alpen-fictional.{DOMAIN}/leistungen",
            industry="Logistics (fixture)",
            product_focus="Fixture product focus: freight consolidation.",
            recommended_buyer_roles=["Head of Logistics (fixture)"],
        )
    if not fx5.ggd_outreach_approved:
        fx5.ggd_prepare_draft(
            subject="Fixture subject: Germany Growth Desk introduction (synthetic sent fixture)",
            body="Fixture body -- synthetic sent-state fixture, never actually mailed.",
        )
        fx5.write(
            {
                "ggd_contact_basis": "consent",
                "ggd_contact_basis_note": VALID_BASIS_NOTE,
            }
        )
        fx5.action_ggd_approve_outreach()
    # Required shape, enforced by _ggd_check_send_key_matches_approved_draft:
    # "<opportunity id>:<approved draft version>".
    FX5_SEND_KEY = f"{fx5.id}:{fx5.ggd_approved_draft_version}"
    fx5.ggd_claim_send_key(FX5_SEND_KEY)
    fx5.ggd_finalize_send(
        message_id=FX5_MESSAGE_ID,
        recipient=fx5.ggd_approved_recipient,
        subject=fx5.ggd_draft_subject,
        body_summary="Fixture body summary: synthetic sent-state fixture for Workflow 4 tests.",
    )

# ---------------------------------------------------------------------------
# FX6A / FX6B -- two minimal leads sharing one email address, so
# ggd_find_reply_candidates(sender_email=...) returns more than one
# candidate. Used only for the "ambiguous match" Workflow 4 test case;
# deliberately kept separate from every other fixture's email so it cannot
# make FX2/FX4/FX5's single-match tests ambiguous by accident.
# ---------------------------------------------------------------------------
FX6_EMAIL = f"fx6-ambiguous@{DOMAIN}"
fx6a_name = f"{FIXTURE_PREFIX} FX6A -- Ambiguous Match Pair 1 (Fictional Duplicate Contact)"
fx6a, fx6a_new = get_or_create(
    "FX6A_AMBIGUOUS",
    fx6a_name,
    {
        "name": fx6a_name,
        "type": "opportunity",
        "email_from": FX6_EMAIL,
        "description": "Gate 3 fixture. Shares its email with FX6B on purpose (ambiguous-match test).",
    },
)
fx6b_name = f"{FIXTURE_PREFIX} FX6B -- Ambiguous Match Pair 2 (Fictional Duplicate Contact)"
fx6b, fx6b_new = get_or_create(
    "FX6B_AMBIGUOUS",
    fx6b_name,
    {
        "name": fx6b_name,
        "type": "opportunity",
        "email_from": FX6_EMAIL,
        "description": "Gate 3 fixture. Shares its email with FX6A on purpose (ambiguous-match test).",
    },
)

# ---------------------------------------------------------------------------
# FX7 -- built exactly like FX5 (real ggd_claim_send_key/ggd_finalize_send
# path, its own synthetic Message-ID, no SMTP call), then a SEPARATE
# follow-up write backdates ggd_send_confirmed_at, ggd_last_sent_at, and
# ggd_last_message_date by 8 days so it clears BOTH staleness checks that
# gate Workflow 5:
#   - the n8n candidate query domain in
#     workflows/GGD-05-daily-follow-up.json ("Select stale contacted
#     opportunities": ggd_send_confirmed_at <= now - 7 days, read-only
#     reference, not edited here), and
#   - ggd_queue_follow_up()'s own guard (crm_lead.py: raises "not yet seven
#     days old" when ggd_send_confirmed_at is within the last 7 days).
# No reply is recorded for FX7 on purpose, so ggd_last_reply_received_at
# stays empty and does not block ggd_queue_follow_up()'s reply check.
#
# Read-only check of write() before writing this: the backdating write below
# touches only ggd_send_confirmed_at, ggd_last_sent_at, and
# ggd_last_message_date. None of write()'s special branches trigger on
# those field names -- they only trigger when the write's values contain a
# GGD_APPROVAL_INPUT_FIELDS member (ggd_draft_subject/body/version,
# email_from), a GGD_DRAFT_FIELDS member, ggd_last_send_key,
# ggd_do_not_contact, or ggd_outreach_approved. None of those keys are in
# this write, so it falls straight through to super().write(values), i.e.
# an ordinary field update. No blocker found; nothing was worked around.
# ---------------------------------------------------------------------------
fx7_name = f"{FIXTURE_PREFIX} FX7 -- Stale Confirmed Send, For Follow-Up Queue Test (Ostsee Fictional Feinmechanik OHG)"
fx7, fx7_new = get_or_create(
    "FX7_STALE_FOLLOWUP",
    fx7_name,
    {
        "name": fx7_name,
        "type": "opportunity",
        "email_from": f"fx7@{DOMAIN}",
        "description": (
            "Gate 3 fixture. Reached its confirmed-sent state via the real "
            "ggd_claim_send_key/ggd_finalize_send methods (no SMTP call, no "
            "email sent), then had ggd_send_confirmed_at/ggd_last_sent_at/"
            "ggd_last_message_date backdated by 8 days in a separate write "
            "so it clears Workflow 5's 7-day staleness filter. No reply is "
            "recorded for this record on purpose."
        ),
        "stage_id": stage("Contacted").id or False,
    },
)
FX7_MESSAGE_ID = f"<gate3-fixture-fx7-001@{DOMAIN}>"
FX7_SEND_KEY = fx7.ggd_last_confirmed_send_key or None
if not fx7.ggd_send_confirmed_at:
    if fx7.ggd_qualification_state != "ready":
        fx7.ggd_apply_qualification(
            fit_score=70,
            summary="Fixture fit assessment: fictional precision-parts subcontractor.",
            personalization_angle="Fixture angle: fictional recent production-capacity expansion.",
            confidence=0.8,
            source_url=f"https://www.ostsee-fictional.{DOMAIN}/fertigung",
            industry="Precision engineering (fixture)",
            product_focus="Fixture product focus: contract machining.",
            recommended_buyer_roles=["Purchasing Manager (fixture)"],
        )
    if not fx7.ggd_outreach_approved:
        fx7.ggd_prepare_draft(
            subject="Fixture subject: Germany Growth Desk introduction (stale follow-up fixture)",
            body="Fixture body -- stale-send fixture for Workflow 5 testing, never actually mailed.",
        )
        fx7.write(
            {
                "ggd_contact_basis": "consent",
                "ggd_contact_basis_note": VALID_BASIS_NOTE,
            }
        )
        fx7.action_ggd_approve_outreach()
    FX7_SEND_KEY = f"{fx7.id}:{fx7.ggd_approved_draft_version}"
    fx7.ggd_claim_send_key(FX7_SEND_KEY)
    fx7.ggd_finalize_send(
        message_id=FX7_MESSAGE_ID,
        recipient=fx7.ggd_approved_recipient,
        subject=fx7.ggd_draft_subject,
        body_summary="Fixture body summary: stale confirmed-send fixture for Workflow 5 follow-up tests.",
    )

FX7_BACKDATE_TARGET = datetime.now() - timedelta(days=8)
if fx7.ggd_send_confirmed_at and fx7.ggd_send_confirmed_at > FX7_BACKDATE_TARGET:
    # Separate write from the finalize step above and from any approval
    # change -- purely backdating three date/datetime fields. Idempotent:
    # once ggd_send_confirmed_at is already <= the freshly-recomputed
    # 8-days-ago target (true on every later re-run, since a previously
    # backdated timestamp only gets further in the past relative to "now"),
    # this condition is false and nothing is written.
    fx7.write(
        {
            "ggd_send_confirmed_at": FX7_BACKDATE_TARGET,
            "ggd_last_sent_at": FX7_BACKDATE_TARGET,
            "ggd_last_message_date": FX7_BACKDATE_TARGET.date(),
        }
    )

env.cr.commit()

print("")
print("========================================")
print("Gate 3 fixture summary")
print("========================================")
for key, rec_id, name in created:
    print(f"CREATED  {key:22s} id={rec_id:<6d} {name}")
for key, rec_id, name in existing:
    print(f"EXISTS   {key:22s} id={rec_id:<6d} {name}")
print("")
print(f"FX5 synthetic message-id: {FX5_MESSAGE_ID}")
print(f"FX5 send key (id:approved_draft_version): {FX5_SEND_KEY}")
print(f"FX6 shared ambiguous email: {FX6_EMAIL}")
print(f"FX7 synthetic message-id: {FX7_MESSAGE_ID}")
print(f"FX7 send key (id:approved_draft_version): {FX7_SEND_KEY}")
print(f"FX7 ggd_send_confirmed_at after backdating: {fx7.ggd_send_confirmed_at}")
print("Re-run this script any time; it will report EXISTS and create nothing new.")
PYEOF

echo ""
echo "Fixture run complete. Copy the CREATED/EXISTS lines above into"
echo "docs/handoffs/CLAUDE-CODE.md if this was run outside that session."
