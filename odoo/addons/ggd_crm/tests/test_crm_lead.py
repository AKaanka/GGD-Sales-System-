"""Control tests for the GGD outreach approval gate.

These cover the non-negotiable rules in PLAN.md and the contact-basis
enforcement described in docs/LAWFUL-CONTACT-PROCEDURE.md section 8. The point
of the suite is that the gate is verified rather than assumed: it must hold
through the approval button, through a direct write, and through create.

Run:
    docker compose exec odoo odoo -d ggd --test-enable \\
        --test-tags /ggd_crm --stop-after-init -u ggd_crm
"""

from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

VALID_NOTE = "Opt-in via website form 2026-03-04, record ref WEB-1183."


@tagged("post_install", "-at_install")
class TestGgdOutreachApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env["crm.lead"]

    def _lead(self, **values):
        base = {
            "name": "QA fixture opportunity",
            "email_from": "control-test@ggd-qa.invalid",
        }
        base.update(values)
        return self.Lead.create(base)

    def _approved_lead(self, **values):
        """A fixture whose approval is committed, so a send key can be claimed.

        The claim guard re-reads approval, suppression and lawful-basis state
        from the stored row, so a bare lead can no longer claim a key. Going
        through the approval button is what stamps approver, approval time and
        basis-verified time, which the guard also requires.
        """
        base = {
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
        }
        base.update(values)
        lead = self._lead(**base)
        lead.action_ggd_approve_outreach()
        return lead

    def _claimed_lead(self, **values):
        """An approved lead whose send key is claimed, ready to be finalised.

        ggd_finalize_send() now refuses a record with no claim, so the send
        path has to be walked properly: approve, then claim, then finalise.
        """
        lead = self._approved_lead(**values)
        self.assertTrue(lead.ggd_claim_send_key("%s-2026-08-20 09:15:00" % lead.id))
        return lead

    # ------------------------------------------------------------------
    # Approval refusals
    # ------------------------------------------------------------------

    def test_approve_refused_without_contact_basis(self):
        lead = self._lead(ggd_contact_basis_note=VALID_NOTE)
        with self.assertRaises(ValidationError):
            lead.action_ggd_approve_outreach()
        self.assertFalse(lead.ggd_outreach_approved)

    def test_approve_refused_when_do_not_contact(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_do_not_contact=True,
        )
        with self.assertRaises(ValidationError):
            lead.action_ggd_approve_outreach()
        self.assertFalse(lead.ggd_outreach_approved)

    def test_approve_refused_on_no_email_bases(self):
        """referral, other and trade-fair-without-opt-in are not consent.

        This is the material finding in LAWFUL-CONTACT-PROCEDURE.md section 3:
        these values record where a contact came from, not permission to email
        it.
        """
        for basis in self.Lead.GGD_NO_EMAIL_BASES:
            with self.subTest(basis=basis):
                lead = self._lead(
                    ggd_contact_basis=basis,
                    ggd_contact_basis_note=VALID_NOTE,
                )
                with self.assertRaises(ValidationError):
                    lead.action_ggd_approve_outreach()
                self.assertFalse(lead.ggd_outreach_approved)

    def test_approve_refused_when_note_missing_or_thin(self):
        for note in (False, "", "   ", "ok"):
            with self.subTest(note=note):
                lead = self._lead(
                    ggd_contact_basis="consent",
                    ggd_contact_basis_note=note,
                )
                with self.assertRaises(ValidationError):
                    lead.action_ggd_approve_outreach()
                self.assertFalse(lead.ggd_outreach_approved)

    # ------------------------------------------------------------------
    # Approval success and metadata
    # ------------------------------------------------------------------

    def test_approve_succeeds_and_stamps_metadata(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )
        lead.action_ggd_approve_outreach()

        self.assertTrue(lead.ggd_outreach_approved)
        self.assertEqual(lead.ggd_outreach_approved_by, self.env.user)
        self.assertTrue(lead.ggd_outreach_approved_at)
        self.assertTrue(
            lead.ggd_contact_basis_verified_at,
            "Approving must stamp the basis-verified time so evidence age is visible.",
        )

    def test_revoke_clears_all_approval_metadata(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )
        lead.action_ggd_approve_outreach()
        lead.action_ggd_revoke_outreach()

        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertFalse(lead.ggd_contact_basis_verified_at)

    # ------------------------------------------------------------------
    # Suppression overrides approval
    # ------------------------------------------------------------------

    def test_do_not_contact_clears_approval_on_write(self):
        """Suppression must take effect in the same write, not later."""
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )
        lead.action_ggd_approve_outreach()

        lead.write({"ggd_do_not_contact": True})

        self.assertTrue(lead.ggd_do_not_contact)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertFalse(lead.ggd_contact_basis_verified_at)

    # ------------------------------------------------------------------
    # The gate must not be bypassable
    # ------------------------------------------------------------------

    def test_direct_write_cannot_bypass_the_gate(self):
        """A gate enforced only in the UI button is not a gate."""
        lead = self._lead(
            ggd_contact_basis="referral",
            ggd_contact_basis_note=VALID_NOTE,
        )
        with self.assertRaises(ValidationError):
            lead.write({"ggd_outreach_approved": True})
        self.assertFalse(lead.ggd_outreach_approved)

    def test_direct_write_cannot_bypass_the_note_requirement(self):
        lead = self._lead(ggd_contact_basis="consent")
        with self.assertRaises(ValidationError):
            lead.write({"ggd_outreach_approved": True})
        self.assertFalse(lead.ggd_outreach_approved)

    def test_create_cannot_bypass_the_gate(self):
        """A record must not come into existence already approved on a basis
        that could never have been approved afterwards."""
        with self.assertRaises(ValidationError):
            self._lead(
                ggd_contact_basis="other",
                ggd_contact_basis_note=VALID_NOTE,
                ggd_outreach_approved=True,
            )

    def test_create_approved_allowed_on_a_sound_basis(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_outreach_approved=True,
        )
        self.assertTrue(lead.ggd_outreach_approved)

    def test_create_with_do_not_contact_is_never_approved(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_do_not_contact=True,
            ggd_outreach_approved=True,
        )
        self.assertFalse(lead.ggd_outreach_approved)

    def test_direct_write_approval_stamps_metadata(self):
        """Approval by any route must leave approver and timestamp behind.

        The send key is derived from the approval time. A record approved
        without one cannot be revoked, re-approved and sent again, because the
        key would not change.
        """
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )
        lead.write({"ggd_outreach_approved": True})

        self.assertTrue(lead.ggd_outreach_approved)
        self.assertTrue(lead.ggd_outreach_approved_at)
        self.assertEqual(lead.ggd_outreach_approved_by, self.env.user)
        self.assertTrue(lead.ggd_contact_basis_verified_at)

    def test_create_approved_stamps_metadata(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_outreach_approved=True,
        )
        self.assertTrue(lead.ggd_outreach_approved_at)
        self.assertEqual(lead.ggd_outreach_approved_by, self.env.user)

    def test_create_with_a_send_key_is_rejected(self):
        """A record must not come into existence with a send already claimed.

        create() does not pass through the locked approval check in write(), so
        a key accepted here would be a claim nobody ever validated.
        """
        before = self.Lead.search_count([])

        with self.assertRaises(ValidationError):
            self._lead(ggd_last_send_key="7-2026-08-20 09:15:00")

        self.assertEqual(
            self.Lead.search_count([]),
            before,
            "The rejected create must not leave a record behind.",
        )

    def test_create_with_an_empty_send_key_is_allowed(self):
        """Only a non-empty key is a claim; an explicit blank stays harmless."""
        lead = self._lead(ggd_last_send_key=False)
        self.assertFalse(lead.ggd_last_send_key)

    # ------------------------------------------------------------------
    # Duplicate-send protection
    # ------------------------------------------------------------------

    def test_send_key_can_be_claimed_once(self):
        lead = self._approved_lead()
        self.assertTrue(lead.ggd_claim_send_key("7-42"))
        self.assertEqual(lead.ggd_last_send_key, "7-42")
        self.assertTrue(lead.ggd_last_sent_at)

    def test_second_claim_of_same_key_is_refused(self):
        """This is the control that prevents a duplicate send."""
        lead = self._approved_lead()
        lead.ggd_claim_send_key("7-42")
        self.assertFalse(lead.ggd_claim_send_key("7-42"))

    def test_a_new_draft_produces_a_claimable_key(self):
        """A genuinely new draft must still be sendable."""
        lead = self._approved_lead()
        lead.ggd_claim_send_key("7-42")
        self.assertTrue(lead.ggd_claim_send_key("7-43"))
        self.assertEqual(lead.ggd_last_send_key, "7-43")

    def test_empty_send_key_is_refused(self):
        """Checked before anything is locked, so a bare lead is enough."""
        lead = self._lead()
        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(False)

    # ------------------------------------------------------------------
    # Field constraints relied on by the automation layer
    # ------------------------------------------------------------------

    def test_ai_confidence_must_be_between_zero_and_one(self):
        lead = self._lead()
        for bad in (-0.1, 1.5):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    lead.write({"ggd_ai_confidence": bad})

    def test_ai_confidence_accepts_the_boundaries(self):
        lead = self._lead()
        for good in (0.0, 0.5, 1.0):
            with self.subTest(value=good):
                lead.write({"ggd_ai_confidence": good})
                self.assertAlmostEqual(lead.ggd_ai_confidence, good, places=2)

    def test_fit_score_must_be_between_zero_and_one_hundred(self):
        lead = self._lead()
        for bad in (-1, 101):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    lead.write({"ggd_fit_score": bad})

    # ------------------------------------------------------------------
    # Work-selection layer: send finalization and idempotency
    # ------------------------------------------------------------------

    def test_finalize_send_updates_all_fields(self):
        """Verify finalize_send() atomically marks send complete and revokes approval."""
        from odoo import fields

        lead = self._claimed_lead()

        # Verify initial state
        self.assertTrue(lead.ggd_outreach_approved)
        self.assertIsNotNone(lead.ggd_outreach_approved_at)

        # Call finalize_send
        lead.ggd_finalize_send()

        # Verify all fields updated
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertEqual(lead.ggd_last_message_date, fields.Date.today())

        # Verify chatter note created
        messages = lead.message_ids.filtered(
            lambda m: "GGD outreach sent" in (m.body or "")
        )
        self.assertTrue(messages, "Chatter note not created")

    def test_finalize_send_revokes_approval_atomically(self):
        """Finalize revokes approval in one atomic write."""
        lead = self._claimed_lead()

        # Before finalize, approval is set
        self.assertTrue(lead.ggd_outreach_approved)

        lead.ggd_finalize_send()

        # After finalize, approval is cleared (prevents automatic resends)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)

        # But record can be re-approved if conditions still met (that's okay)
        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)

    def test_last_message_date_set_on_finalize(self):
        """ggd_last_message_date is set to today when send finalizes."""
        from odoo import fields

        lead = self._claimed_lead()
        self.assertFalse(lead.ggd_last_message_date)

        lead.ggd_finalize_send()

        self.assertEqual(lead.ggd_last_message_date, fields.Date.today())

    def test_finalize_without_a_claim_is_refused(self):
        """Finalising an unclaimed record would forge a sent audit.

        The claim is the only evidence the record passed the locked outbound
        gate. Without it there is nothing to finalise, and nothing may be
        written: no follow-up date, no sent note, and no consumed approval.
        """
        lead = self._approved_lead()
        self.assertFalse(lead.ggd_last_send_key)

        with self.assertRaises(ValidationError):
            lead.ggd_finalize_send()

        self.assertFalse(
            lead.ggd_last_message_date,
            "A refused finalisation must not set a follow-up date.",
        )
        self.assertFalse(
            lead.message_ids.filtered(lambda m: "GGD outreach sent" in (m.body or "")),
            "A refused finalisation must not post a sent audit note.",
        )
        self.assertTrue(
            lead.ggd_outreach_approved,
            "A refused finalisation must not consume the approval either.",
        )

    def test_finalize_without_a_send_time_is_refused(self):
        """A key with no stamped send time is not a completed claim."""
        lead = self._claimed_lead()
        lead.write({"ggd_last_sent_at": False})

        with self.assertRaises(ValidationError):
            lead.ggd_finalize_send()

        self.assertFalse(lead.ggd_last_message_date)
        self.assertFalse(
            lead.message_ids.filtered(lambda m: "GGD outreach sent" in (m.body or ""))
        )

    def test_last_message_date_persists_across_writes(self):
        """ggd_last_message_date is not cleared by normal write operations."""
        from odoo import fields

        lead = self._lead()
        today = fields.Date.today()
        lead.ggd_last_message_date = today

        # Write other fields — message date should persist
        lead.write({"name": "Updated name"})

        self.assertEqual(lead.ggd_last_message_date, today)

    def test_send_key_claim_before_finalize(self):
        """Typical send workflow: claim key, then finalize."""
        from odoo import fields

        lead = self._approved_lead()

        # Step 1: Claim send key
        can_send = lead.ggd_claim_send_key("order-123-send-v1")
        self.assertTrue(can_send)
        self.assertEqual(lead.ggd_last_send_key, "order-123-send-v1")
        self.assertIsNotNone(lead.ggd_last_sent_at)

        # Step 2: Finalize (after SMTP succeeds)
        lead.ggd_finalize_send()
        self.assertEqual(lead.ggd_last_message_date, fields.Date.today())

        # Step 3: Verify idempotency - re-claim same key returns False.
        # Finalizing revoked approval, so this also proves the duplicate check
        # runs before the approval check: an already-sent key must report
        # False, not "not approved".
        can_resend = lead.ggd_claim_send_key("order-123-send-v1")
        self.assertFalse(can_resend)

    # ------------------------------------------------------------------
    # Atomic claim: the guard the live n8n workflow actually reaches
    #
    # The deployed "Claim send key before SMTP" node does NOT call
    # ggd_claim_send_key(). It performs an ordinary Odoo record update. These
    # tests therefore exercise the plain write() path as well as the method,
    # because the plain path is the one that has to fail closed in production.
    #
    # The workflow decides whether a send is lawful from a snapshot taken
    # several RPCs before the claim. Everything in that snapshot is re-read
    # under the claim's row lock, so the tests below drive the two states
    # apart on purpose: approve, then change the record, then claim.
    #
    # Limitation, stated deliberately. A true two-connection concurrency test
    # is not possible inside TransactionCase. A second cursor is a separate
    # database connection and cannot see fixture rows created in this test's
    # uncommitted transaction, so proving a real lock wait would mean
    # committing fixtures to the developer's database and leaving them behind
    # whenever the test failed. That trade is not worth it here. The strongest
    # safe substitute is used instead: test_guard_reads_the_database_row
    # proves the property the race actually turns on, namely that the guard
    # reads the stored row rather than the ORM cache. A cached read is what
    # makes a duplicate send possible; reading under FOR UPDATE is what closes
    # it. A genuine two-connection test belongs in an integration suite
    # against a disposable database, not in this file.
    # ------------------------------------------------------------------

    def _key(self, lead):
        """The key shape the live workflow builds: id plus approval time."""
        return "%s-2026-08-20 09:15:00" % lead.id

    # -------------------------------- committed approval is a precondition

    def test_claim_without_committed_approval_is_rejected(self):
        """A bare record must not be claimable by either route."""
        lead = self._lead()

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(self._key(lead))

        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": self._key(lead)})

        self.assertFalse(lead.ggd_last_send_key)
        self.assertFalse(lead.ggd_last_sent_at)

    def test_claim_after_committed_approval_succeeds(self):
        lead = self._approved_lead()

        self.assertTrue(lead.ggd_claim_send_key(self._key(lead)))
        self.assertEqual(lead.ggd_last_send_key, self._key(lead))
        self.assertTrue(lead.ggd_last_sent_at)

    def test_approval_and_claim_in_one_write_is_rejected(self):
        """Human approval must be committed before a claim starts.

        Otherwise a single n8n update could grant approval and claim the send
        in the same breath, and no human would ever have seen the record.
        """
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )

        with self.assertRaises(ValidationError):
            lead.write(
                {
                    "ggd_outreach_approved": True,
                    "ggd_last_send_key": self._key(lead),
                }
            )

        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_last_send_key)

    # ------------------- state that changed after the workflow's snapshot

    def test_revocation_between_workflow_read_and_claim_is_rejected(self):
        lead = self._approved_lead()
        key = self._key(lead)

        # What the workflow read several RPCs earlier.
        self.assertTrue(lead.ggd_outreach_approved)

        # A human revokes in the meantime.
        lead.action_ggd_revoke_outreach()

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(key)
        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": key})

        self.assertFalse(lead.ggd_last_send_key)

    def test_do_not_contact_between_workflow_read_and_claim_is_rejected(self):
        lead = self._approved_lead()
        key = self._key(lead)

        self.assertTrue(lead.ggd_outreach_approved)

        lead.write({"ggd_do_not_contact": True})

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(key)
        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": key})

        self.assertFalse(lead.ggd_last_send_key)

    def test_missing_approval_metadata_is_rejected(self):
        """Approver, approval time and verification time are all required.

        Each is cleared on its own, leaving ggd_outreach_approved true, so the
        test proves the guard checks the metadata rather than just the flag.
        """
        for field_name in (
            "ggd_outreach_approved_by",
            "ggd_outreach_approved_at",
            "ggd_contact_basis_verified_at",
        ):
            with self.subTest(field=field_name):
                lead = self._approved_lead()
                lead.write({field_name: False})
                self.assertTrue(lead.ggd_outreach_approved)

                with self.assertRaises(ValidationError):
                    lead.ggd_claim_send_key(self._key(lead))
                with self.assertRaises(ValidationError):
                    lead.write({"ggd_last_send_key": self._key(lead)})

                self.assertFalse(lead.ggd_last_send_key)

    def test_disallowed_contact_basis_is_rejected(self):
        """A basis downgraded after approval must stop the send.

        Approval happened on consent; the basis is then changed to one that is
        never lawful for a first marketing email. The approval flag is still
        true, so only a fresh read of the basis catches this.
        """
        for basis in self.Lead.GGD_NO_EMAIL_BASES:
            with self.subTest(basis=basis):
                lead = self._approved_lead()
                lead.write({"ggd_contact_basis": basis})
                self.assertTrue(lead.ggd_outreach_approved)

                with self.assertRaises(ValidationError):
                    lead.ggd_claim_send_key(self._key(lead))
                with self.assertRaises(ValidationError):
                    lead.write({"ggd_last_send_key": self._key(lead)})

                self.assertFalse(lead.ggd_last_send_key)

    def test_missing_contact_basis_is_rejected(self):
        lead = self._approved_lead()
        lead.write({"ggd_contact_basis": False})

        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": self._key(lead)})
        self.assertFalse(lead.ggd_last_send_key)

    def test_thin_contact_basis_note_is_rejected(self):
        lead = self._approved_lead()
        lead.write({"ggd_contact_basis_note": "ok"})

        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": self._key(lead)})
        self.assertFalse(lead.ggd_last_send_key)

    def test_blocked_claim_message_does_not_leak_stored_values(self):
        """Reasons cross the RPC boundary into n8n logs; row contents must not."""
        lead = self._approved_lead(
            ggd_contact_basis_note="Opt-in ref SECRET-EVIDENCE-1183 on file.",
        )
        lead.write({"ggd_contact_basis": "referral"})

        with self.assertRaises(ValidationError) as caught:
            lead.write({"ggd_last_send_key": self._key(lead)})

        message = str(caught.exception)
        self.assertNotIn("SECRET-EVIDENCE-1183", message)
        self.assertNotIn("referral", message)

    # ------------------------------------------- suppression always wins

    def test_suppression_write_carrying_a_key_still_suppresses(self):
        """Requirement: the guard must never roll back a suppression.

        A write that marks Do not contact while also carrying a send key must
        succeed, must clear approval, and must not leave a claim behind.
        """
        lead = self._approved_lead()

        lead.write(
            {
                "ggd_last_send_key": self._key(lead),
                "ggd_do_not_contact": True,
            }
        )

        self.assertTrue(lead.ggd_do_not_contact)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertFalse(lead.ggd_contact_basis_verified_at)
        self.assertFalse(
            lead.ggd_last_send_key,
            "A suppression is not a send and must not establish a claim.",
        )

    def test_revocation_write_carrying_a_key_still_revokes(self):
        lead = self._approved_lead()

        lead.write(
            {
                "ggd_last_send_key": self._key(lead),
                "ggd_outreach_approved": False,
            }
        )

        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertFalse(lead.ggd_contact_basis_verified_at)
        self.assertFalse(lead.ggd_last_send_key)

    def test_suppression_wins_even_over_a_duplicate_key(self):
        """The duplicate guard must not block a suppression either."""
        lead = self._approved_lead()
        key = self._key(lead)
        lead.ggd_claim_send_key(key)

        lead.write({"ggd_last_send_key": key, "ggd_do_not_contact": True})

        self.assertTrue(lead.ggd_do_not_contact)
        self.assertFalse(lead.ggd_outreach_approved)

    # ------------------------------------------------- duplicate behaviour

    def test_plain_write_of_the_same_key_is_rejected(self):
        """The exact shape of the live n8n update node, run twice."""
        lead = self._approved_lead()
        key = self._key(lead)

        lead.write({"ggd_last_send_key": key})
        self.assertEqual(lead.ggd_last_send_key, key)

        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": key})

    def test_plain_write_of_a_new_key_stamps_sent_at(self):
        lead = self._approved_lead()
        self.assertFalse(lead.ggd_last_sent_at)

        lead.write({"ggd_last_send_key": self._key(lead)})

        self.assertTrue(
            lead.ggd_last_sent_at,
            "A claim marks the send as in flight and must record when.",
        )

    def test_caller_supplied_sent_at_is_not_overwritten(self):
        lead = self._approved_lead()
        supplied = datetime(2026, 8, 20, 9, 15, 0)

        lead.write(
            {
                "ggd_last_send_key": self._key(lead),
                "ggd_last_sent_at": supplied,
            }
        )

        self.assertEqual(lead.ggd_last_sent_at, supplied)

    def test_guard_reads_the_database_row(self):
        """The property that makes the race closable.

        The claim is written straight to SQL to simulate one a competing
        execution has just committed. That leaves this transaction's ORM cache
        holding the pre-claim value, which is the situation a racing execution
        is in. A guard that trusted the cache would see an empty key and allow
        a second send.
        """
        lead = self._approved_lead()
        self.assertFalse(lead.ggd_last_send_key)

        key = self._key(lead)
        self.env.cr.execute(
            "UPDATE crm_lead SET ggd_last_send_key = %s WHERE id = %s",
            (key, lead.id),
        )

        with self.assertRaises(ValidationError):
            lead.write({"ggd_last_send_key": key})

    def test_claim_refused_when_the_row_is_already_claimed(self):
        """Same simulation, through the method's contract: False, not a raise."""
        lead = self._approved_lead()
        self.assertFalse(lead.ggd_last_send_key)

        key = self._key(lead)
        self.env.cr.execute(
            "UPDATE crm_lead SET ggd_last_send_key = %s WHERE id = %s",
            (key, lead.id),
        )

        self.assertFalse(lead.ggd_claim_send_key(key))

    def test_a_later_approval_produces_a_claimable_key(self):
        """Revoke and re-approve must still be sendable.

        The key the workflow builds is opportunity id plus approval time, so a
        fresh approval yields a fresh key. Fixed timestamps are used rather
        than real approvals because Odoo truncates datetimes to whole seconds;
        see the note about same-second re-approval in the review.
        """
        lead = self._approved_lead()
        first_approval = "%s-2026-08-20 09:15:00" % lead.id
        second_approval = "%s-2026-08-20 11:42:00" % lead.id

        self.assertTrue(lead.ggd_claim_send_key(first_approval))
        self.assertFalse(lead.ggd_claim_send_key(first_approval))
        self.assertTrue(lead.ggd_claim_send_key(second_approval))
        self.assertEqual(lead.ggd_last_send_key, second_approval)

    def test_clearing_the_send_key_is_not_blocked(self):
        """Only a non-empty key is a claim, so manual recovery stays possible."""
        lead = self._approved_lead()
        key = self._key(lead)
        lead.write({"ggd_last_send_key": key})

        lead.write({"ggd_last_send_key": False})

        self.assertFalse(lead.ggd_last_send_key)
        self.assertTrue(lead.ggd_claim_send_key(key))

    # ---------------------------------------------- lock shape and contract

    def test_rows_are_locked_in_ascending_id_order(self):
        """Deterministic lock ordering is what prevents deadlocks.

        The helper builds its result in the order it takes locks, so the key
        order of the returned mapping is the lock order.
        """
        first = self._lead()
        second = self._lead()
        third = self._lead()
        shuffled = self.Lead.browse([third.id, first.id, second.id])

        self.assertEqual(
            list(shuffled._ggd_lock_outbound_state().keys()),
            sorted([first.id, second.id, third.id]),
        )

    def test_locked_state_carries_every_required_column(self):
        """The whole outbound decision must come from the one locked read."""
        lead = self._approved_lead()

        state = lead._ggd_lock_outbound_state()[lead.id]

        for column in self.Lead.GGD_CLAIM_STATE_COLUMNS:
            self.assertIn(column, state)

    def test_different_leads_do_not_share_a_global_lock(self):
        """The guard is per row, not per table.

        Two opportunities may legitimately carry the same key text. A fix
        implemented as a unique index on the column would break this, so the
        distinction is worth pinning down.
        """
        first = self._approved_lead()
        second = self._approved_lead()
        key = "shared-key-text"

        self.assertTrue(first.ggd_claim_send_key(key))
        self.assertTrue(second.ggd_claim_send_key(key))
        self.assertFalse(first.ggd_claim_send_key(key))

    def test_claim_does_not_swallow_unrelated_validation_errors(self):
        """A refusal from elsewhere must never read as "already sent".

        There is no try/except in ggd_claim_send_key() today, so this is a
        regression guard: if one is ever introduced, an unrelated
        ValidationError must still propagate rather than become a False.
        """
        lead = self._approved_lead()

        def refuse(*args, **kwargs):
            raise ValidationError("Unrelated constraint")

        with patch.object(type(lead), "write", refuse):
            with self.assertRaises(ValidationError):
                lead.ggd_claim_send_key(self._key(lead))

    # ------------------------------------------------------------------
    # Falsy revocation values
    #
    # n8n, the Odoo client and a hand-written RPC call can each express "not
    # approved" as False, 0 or None. All three must be treated identically,
    # both by the revocation branch and by the suppression-wins rule.
    # ------------------------------------------------------------------

    def test_any_falsy_approval_value_clears_the_metadata(self):
        for falsy in (False, 0, None):
            with self.subTest(value=falsy):
                lead = self._approved_lead()
                self.assertTrue(lead.ggd_outreach_approved_by)
                self.assertTrue(lead.ggd_contact_basis_verified_at)

                lead.write({"ggd_outreach_approved": falsy})

                self.assertFalse(lead.ggd_outreach_approved)
                self.assertFalse(
                    lead.ggd_outreach_approved_by,
                    "A revoked record must not keep its approver.",
                )
                self.assertFalse(
                    lead.ggd_outreach_approved_at,
                    "A revoked record must not keep its approval time.",
                )
                self.assertFalse(
                    lead.ggd_contact_basis_verified_at,
                    "A revoked record must not keep its basis-verified time.",
                )

    def test_any_falsy_approval_value_suppresses_a_carried_key(self):
        """Suppression-wins must hold for 0 and None, not only for False."""
        for falsy in (False, 0, None):
            with self.subTest(value=falsy):
                lead = self._approved_lead()

                lead.write(
                    {
                        "ggd_last_send_key": self._key(lead),
                        "ggd_outreach_approved": falsy,
                    }
                )

                self.assertFalse(lead.ggd_outreach_approved)
                self.assertFalse(lead.ggd_outreach_approved_by)
                self.assertFalse(lead.ggd_outreach_approved_at)
                self.assertFalse(lead.ggd_contact_basis_verified_at)
                self.assertFalse(
                    lead.ggd_last_send_key,
                    "A revocation is not a send and must not leave a claim.",
                )

    def test_granting_approval_is_not_read_as_a_revocation(self):
        """The broadened falsy check must not swallow a genuine approval."""
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )

        lead.write({"ggd_outreach_approved": True})

        self.assertTrue(lead.ggd_outreach_approved)
        self.assertTrue(lead.ggd_outreach_approved_by)
        self.assertTrue(lead.ggd_outreach_approved_at)
        self.assertTrue(lead.ggd_contact_basis_verified_at)
