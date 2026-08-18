#!/bin/bash
# Create test fixtures for work-selection layer tests (WS-F1 through WS-F5)
#
# Usage:
#   ./scripts/setup-work-selection-fixtures.sh
#
# Creates fictional opportunities in ggd database without real contact info.
# All use .invalid addresses for test safety.

set -euo pipefail

cd "$(dirname "$0")/.."

FIXTURE_DATE_14_DAYS_AGO=$(date -v-14d '+%Y-%m-%d' 2>/dev/null || date -d '14 days ago' '+%Y-%m-%d')
FIXTURE_DATE_3_DAYS_AGO=$(date -v-3d '+%Y-%m-%d' 2>/dev/null || date -d '3 days ago' '+%Y-%m-%d')
TODAY=$(date '+%Y-%m-%d')
NOW=$(date '+%Y-%m-%d %H:%M:%S')

echo "Creating work-selection test fixtures..."

docker compose exec -T odoo odoo shell -d ggd <<'EOF'
from datetime import datetime, timedelta

today = datetime.now().date()
fourteen_days_ago = today - timedelta(days=14)
three_days_ago = today - timedelta(days=3)

VALID_NOTE = "Opt-in via website form 2026-03-04, record ref WEB-1183."

print("  WS-F1: Approved opportunity...", end="", flush=True)
ws_f1 = env['crm.lead'].create({
    'name': 'WS-F1: Approved Prospect',
    'email_from': 'ws-f1@ggd-qa.invalid',
    'ggd_contact_basis': 'consent',
    'ggd_contact_basis_note': VALID_NOTE,
    'ggd_do_not_contact': False,
    'ggd_outreach_approved': True,
    'ggd_outreach_approved_by': 2,  # admin user
    'ggd_outreach_approved_at': datetime.now(),
})
print(f" id={ws_f1.id}")

print("  WS-F2: Suppressed prospect...", end="", flush=True)
ws_f2 = env['crm.lead'].create({
    'name': 'WS-F2: Do Not Contact',
    'email_from': 'ws-f2@ggd-qa.invalid',
    'ggd_contact_basis': 'consent',
    'ggd_contact_basis_note': VALID_NOTE,
    'ggd_do_not_contact': True,
})
print(f" id={ws_f2.id}")

print("  WS-F3: Draft pending approval...", end="", flush=True)
ws_f3 = env['crm.lead'].create({
    'name': 'WS-F3: Draft Pending Approval',
    'email_from': 'ws-f3@ggd-qa.invalid',
    'ggd_contact_basis': 'consent',
    'ggd_contact_basis_note': VALID_NOTE,
    'ggd_outreach_approved': False,
})
print(f" id={ws_f3.id}")

print("  WS-F4: 14 days old (stale)...", end="", flush=True)
ws_f4 = env['crm.lead'].create({
    'name': 'WS-F4: 14-Day-Old Message',
    'email_from': 'ws-f4@ggd-qa.invalid',
    'ggd_contact_basis': 'consent',
    'ggd_contact_basis_note': VALID_NOTE,
    'ggd_do_not_contact': False,
    'ggd_last_message_date': fourteen_days_ago,
    'ggd_last_message_id': '<ws-f4-001@example.invalid>',
})
print(f" id={ws_f4.id}")

print("  WS-F5: 3 days old (control)...", end="", flush=True)
ws_f5 = env['crm.lead'].create({
    'name': 'WS-F5: 3-Day-Old Message',
    'email_from': 'ws-f5@ggd-qa.invalid',
    'ggd_contact_basis': 'consent',
    'ggd_contact_basis_note': VALID_NOTE,
    'ggd_do_not_contact': False,
    'ggd_last_message_date': three_days_ago,
    'ggd_last_message_id': '<ws-f5-001@example.invalid>',
})
print(f" id={ws_f5.id}")

print("\n✅ Fixtures created successfully!")
print("\nFixture IDs for your tests:")
print(f"  WS-F1 (id={ws_f1.id}): Approved, ready for send test")
print(f"  WS-F2 (id={ws_f2.id}): Suppressed, for suppression guard test")
print(f"  WS-F3 (id={ws_f3.id}): Pending approval")
print(f"  WS-F4 (id={ws_f4.id}): 14 days old (should be in follow-up query)")
print(f"  WS-F5 (id={ws_f5.id}): 3 days old (should NOT be in follow-up)")
EOF

echo ""
echo "To use these in your workflows:"
echo "  - Copy the IDs above"
echo "  - Use them in Workflow 3/5 manual trigger test inputs"
echo "  - Or reference them in test specs WS-B1 through WS-B8"
