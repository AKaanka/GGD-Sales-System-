#!/usr/bin/env python3
"""Create test fixtures for work-selection layer tests (WS-F1 through WS-F5).

Run from project root:
    docker compose exec odoo python3 /tmp/setup-fixtures.py

Creates fictional opportunities in the ggd database for testing Workflow 3 (approved send)
and Workflow 5 (daily follow-up) without needing to set up real contacts.

Fixtures:
  WS-F1: Approved, unsuppressed, valid basis — ready for send test
  WS-F2: Approved, do-not-contact — guard test
  WS-F3: Draft submitted, no approval yet — queue test
  WS-F4: Sent 14 days ago, no reply — follow-up test
  WS-F5: Sent 3 days ago — follow-up control (not stale yet)

All use .invalid addresses for test safety.
"""

import sys
import os
from datetime import datetime, timedelta

# Add Odoo to path
sys.path.insert(0, "/usr/lib/python3/dist-packages")
sys.path.insert(0, "/usr/lib/python3.12/dist-packages")

os.environ.setdefault("ODOO_CONFIG", "/tmp/setup-fixtures.conf")

import odoo
from odoo.cli import main as odoo_main
from odoo.tools import config

# Create minimal config
if not os.path.exists("/tmp/setup-fixtures.conf"):
    with open("/tmp/setup-fixtures.conf", "w") as f:
        f.write("""
[options]
db_user = odoo
db_password = odoo
db_host = odoo-db
db_port = 5432
db_name = ggd
addons_path = /mnt/extra-addons
""")

# Initialize Odoo
config.parse_config([
    "--config=/tmp/setup-fixtures.conf",
    "-d", "ggd",
    "--without-demo=all",
])

odoo.service.server.setup_logging()
from odoo import api, SUPERUSER_ID
from odoo.modules import get_module_resource

registry = odoo.registry("ggd")

with registry.cursor() as cr:
    with api.Environment(cr, SUPERUSER_ID, {}) as env:
        Lead = env["crm.lead"]

        print("Creating work-selection test fixtures...")

        today = datetime.now().date()
        fourteen_days_ago = today - timedelta(days=14)
        three_days_ago = today - timedelta(days=3)

        VALID_NOTE = "Opt-in via website form 2026-03-04, record ref WEB-1183."

        # WS-F1: Approved, unsuppressed, valid basis
        print("  WS-F1: Approved opportunity (ready for send test)...", end="")
        ws_f1 = Lead.create({
            "name": "WS-F1: Approved Prospect",
            "email_from": "ws-f1@ggd-qa.invalid",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
            "ggd_do_not_contact": False,
            "ggd_outreach_approved": True,
            "ggd_outreach_approved_by": SUPERUSER_ID,
            "ggd_outreach_approved_at": datetime.now(),
        })
        print(f" id={ws_f1.id}")

        # WS-F2: Approved but suppressed (guard test)
        print("  WS-F2: Suppressed prospect (guard test)...", end="")
        ws_f2 = Lead.create({
            "name": "WS-F2: Do Not Contact",
            "email_from": "ws-f2@ggd-qa.invalid",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
            "ggd_do_not_contact": True,
            "ggd_outreach_approved": False,  # Auto-cleared by write() hook
        })
        print(f" id={ws_f2.id}")

        # WS-F3: No approval yet
        print("  WS-F3: Draft submitted, awaiting approval...", end="")
        ws_f3 = Lead.create({
            "name": "WS-F3: Draft Pending Approval",
            "email_from": "ws-f3@ggd-qa.invalid",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
            "ggd_outreach_approved": False,
        })
        print(f" id={ws_f3.id}")

        # WS-F4: Sent 14 days ago (stale, for follow-up test)
        print("  WS-F4: Sent 14 days ago (stale, for follow-up test)...", end="")
        ws_f4 = Lead.create({
            "name": "WS-F4: 14-Day-Old Message",
            "email_from": "ws-f4@ggd-qa.invalid",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
            "ggd_do_not_contact": False,
            "ggd_last_message_date": fourteen_days_ago,
            "ggd_last_message_id": "<ws-f4-001@example.invalid>",
        })
        print(f" id={ws_f4.id}")

        # WS-F5: Sent 3 days ago (not stale, control)
        print("  WS-F5: Sent 3 days ago (not stale, control)...", end="")
        ws_f5 = Lead.create({
            "name": "WS-F5: 3-Day-Old Message",
            "email_from": "ws-f5@ggd-qa.invalid",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
            "ggd_do_not_contact": False,
            "ggd_last_message_date": three_days_ago,
            "ggd_last_message_id": "<ws-f5-001@example.invalid>",
        })
        print(f" id={ws_f5.id}")

        print("\n✅ Fixtures created successfully!")
        print("\nFixture summary:")
        print(f"  WS-F1 (id={ws_f1.id}): Approved, ready for WS-B2 send test")
        print(f"  WS-F2 (id={ws_f2.id}): Suppressed, for WS-B4 guard test")
        print(f"  WS-F3 (id={ws_f3.id}): Draft pending, for approval queue test")
        print(f"  WS-F4 (id={ws_f4.id}): 14 days old, for WS-B6 follow-up query test")
        print(f"  WS-F5 (id={ws_f5.id}): 3 days old (control, should NOT be in follow-up)")
        print("\nUse these IDs in your workflow test inputs or manual triggers.")
