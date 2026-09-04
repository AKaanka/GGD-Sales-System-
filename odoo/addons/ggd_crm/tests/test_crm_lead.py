"""Control tests for the GGD outreach approval gate.

These cover the non-negotiable rules in PLAN.md and the contact-basis
enforcement described in docs/LAWFUL-CONTACT-PROCEDURE.md section 8 (kept on
operational grounds, see docs/COMPLIANCE-SCOPE.md). The point
of the suite is that the gate is verified rather than assumed: it must hold
through the approval button, through a direct write, and through create.

Run:
    docker compose exec odoo odoo -d ggd --test-enable \\
        --test-tags /ggd_crm --stop-after-init -u ggd_crm
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

VALID_NOTE = "Opt-in via website form 2026-03-04, record ref WEB-1183."
VALID_DRAFT_SUBJECT = "A reviewed fictional outreach subject"
VALID_DRAFT_BODY = "Hello, this is a reviewed fictional outreach draft for testing."
VALID_DRAFT_VERSION = "qa-draft-v1"


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
            "ggd_draft_subject": VALID_DRAFT_SUBJECT,
            "ggd_draft_body": VALID_DRAFT_BODY,
            "ggd_draft_version": VALID_DRAFT_VERSION,
            "ggd_draft_status": "ready",
        }
        base.update(values)
        return self.Lead.create(base)

    def _approved_lead(self, **values):
        """A fixture whose approval is committed, so a send key can be claimed.

        The claim guard re-reads approval, suppression and contact-basis state
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
        self.assertTrue(lead.ggd_claim_send_key(self._key(lead)))
        self.assertEqual(
            lead.ggd_claimed_recipient,
            "control-test@ggd-qa.invalid",
        )
        self.assertEqual(lead.ggd_claimed_draft_version, lead.ggd_draft_version)
        return lead

    def _finalize(self, lead, message_id=False):
        """Record a complete fictional SMTP result for a claimed fixture."""
        return lead.ggd_finalize_send(
            message_id or "<qa-%s@example.invalid>" % lead.id,
            lead.email_from,
            lead.ggd_draft_subject,
            "Fictional reviewed body summary.",
        )

    def _make_follow_up_due(self, lead):
        lead.write(
            {"ggd_send_confirmed_at": fields.Datetime.now() - timedelta(days=8)}
        )

    # ------------------------------------------------------------------
    # Approval refusals
    # ------------------------------------------------------------------

    def test_approve_allowed_without_contact_basis(self):
        """Kaan's decision, 4 September 2026: the basis no longer gates approval."""
        lead = self._lead(ggd_contact_basis_note=VALID_NOTE)
        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_contact_basis)

    def test_approve_refused_when_do_not_contact(self):
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_do_not_contact=True,
        )
        with self.assertRaises(ValidationError):
            lead.action_ggd_approve_outreach()
        self.assertFalse(lead.ggd_outreach_approved)

    def test_every_contact_basis_is_approvable_with_evidence(self):
        """No basis is blocked from email any more; the note is the gate.

        Until 2 September 2026 referral, other and trade-fair-without-opt-in
        were refused at approval, a rule derived from German law. The product
        is operated outside the EU (COMPLIANCE-SCOPE.md), so the basis is
        provenance only. What still holds: no basis at all, or a thin note,
        is refused - those tests are elsewhere in this class.
        """
        selection = self.Lead._fields["ggd_contact_basis"].selection
        for basis, _label in selection:
            with self.subTest(basis=basis):
                lead = self._lead(
                    ggd_contact_basis=basis,
                    ggd_contact_basis_note=VALID_NOTE,
                )
                lead.action_ggd_approve_outreach()
                self.assertTrue(lead.ggd_outreach_approved)
                self.assertTrue(lead.ggd_claim_send_key(self._key(lead)))

    def test_approve_allowed_when_note_missing_or_thin(self):
        """The 20-character evidence floor no longer gates approval."""
        for note in (False, "", "   ", "ok"):
            with self.subTest(note=note):
                lead = self._lead(
                    ggd_contact_basis="consent",
                    ggd_contact_basis_note=note,
                )
                lead.action_ggd_approve_outreach()
                self.assertTrue(lead.ggd_outreach_approved)

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
        self.assertEqual(lead.ggd_approved_draft_version, lead.ggd_draft_version)
        self.assertEqual(lead.ggd_approved_recipient, "control-test@ggd-qa.invalid")
        self.assertEqual(lead.ggd_draft_status, "approved")

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
        """A gate enforced only in the UI button is not a gate.

        The contact basis left the gate on 4 September 2026; Do not contact
        did not, and write() must still refuse it exactly as the button does.
        """
        lead = self._lead(
            ggd_contact_basis=False,
            ggd_contact_basis_note=VALID_NOTE,
            ggd_do_not_contact=True,
        )
        with self.assertRaises(ValidationError):
            lead.write({"ggd_outreach_approved": True})
        self.assertFalse(lead.ggd_outreach_approved)

    def test_direct_write_approves_without_a_note(self):
        lead = self._lead(ggd_contact_basis="consent")
        lead.write({"ggd_outreach_approved": True})
        self.assertTrue(lead.ggd_outreach_approved)

    def test_create_approved_without_a_basis_is_allowed(self):
        """Born approved with no basis: permitted now, since a basis is no
        longer something the record could have been refused for later."""
        lead = self._lead(
            ggd_contact_basis=False,
            ggd_contact_basis_note=VALID_NOTE,
            ggd_outreach_approved=True,
        )
        self.assertTrue(lead.ggd_outreach_approved)

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
        """Approval by any route must leave approver and timestamp behind."""
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
        key = self._key(lead)
        self.assertTrue(lead.ggd_claim_send_key(key))
        self.assertEqual(lead.ggd_last_send_key, key)
        self.assertTrue(lead.ggd_last_sent_at)

    def test_second_claim_of_same_key_is_refused(self):
        """This is the control that prevents a duplicate send."""
        lead = self._approved_lead()
        key = self._key(lead)
        lead.ggd_claim_send_key(key)
        self.assertFalse(lead.ggd_claim_send_key(key))

    def test_arbitrary_send_key_is_refused(self):
        lead = self._approved_lead()

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key("retry-with-a-different-key")

        self.assertFalse(lead.ggd_last_send_key)

    def test_a_new_draft_produces_a_claimable_key(self):
        """A genuinely new draft must still be sendable."""
        lead = self._approved_lead()
        first_key = self._key(lead)
        lead.ggd_claim_send_key(first_key)
        self._finalize(lead, "<qa-first@example.invalid>")

        lead.ggd_prepare_draft("Second reviewed subject", "Second reviewed body")
        lead.action_ggd_approve_outreach()
        second_key = self._key(lead)

        self.assertNotEqual(second_key, first_key)
        self.assertTrue(lead.ggd_claim_send_key(second_key))
        self.assertEqual(lead.ggd_last_send_key, second_key)

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
        self._finalize(lead)

        # Verify all fields updated
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)
        self.assertEqual(lead.ggd_last_message_date, fields.Date.today())

        # Verify chatter note created
        messages = lead.message_ids.filtered(
            lambda m: "GGD outreach accepted by SMTP" in (m.body or "")
        )
        self.assertTrue(messages, "Chatter note not created")

    def test_finalize_send_revokes_approval_atomically(self):
        """Finalize revokes approval in one atomic write."""
        lead = self._claimed_lead()

        # Before finalize, approval is set
        self.assertTrue(lead.ggd_outreach_approved)

        self._finalize(lead)

        # After finalize, approval is cleared (prevents automatic resends)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_outreach_approved_by)
        self.assertFalse(lead.ggd_outreach_approved_at)

        # A newly prepared draft can be approved for a later send.
        lead.ggd_prepare_draft("Later reviewed subject", "Later reviewed body")
        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)

    def test_last_message_date_set_on_finalize(self):
        """ggd_last_message_date is set to today when send finalizes."""
        from odoo import fields

        lead = self._claimed_lead()
        self.assertFalse(lead.ggd_last_message_date)

        self._finalize(lead)

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
            self._finalize(lead)

        self.assertFalse(
            lead.ggd_last_message_date,
            "A refused finalisation must not set a follow-up date.",
        )
        self.assertFalse(
            lead.message_ids.filtered(
                lambda m: "GGD outreach accepted by SMTP" in (m.body or "")
            ),
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
            self._finalize(lead)

        self.assertFalse(lead.ggd_last_message_date)
        self.assertFalse(
            lead.message_ids.filtered(
                lambda m: "GGD outreach accepted by SMTP" in (m.body or "")
            )
        )

    def test_finalize_without_complete_smtp_audit_is_refused(self):
        lead = self._claimed_lead()

        with self.assertRaises(ValidationError):
            lead.ggd_finalize_send()

        self.assertFalse(lead.ggd_send_confirmed_at)
        self.assertTrue(lead.ggd_outreach_approved)

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
        key = self._key(lead)
        can_send = lead.ggd_claim_send_key(key)
        self.assertTrue(can_send)
        self.assertEqual(lead.ggd_last_send_key, key)
        self.assertIsNotNone(lead.ggd_last_sent_at)

        # Step 2: Finalize (after SMTP succeeds)
        self._finalize(lead)
        self.assertEqual(lead.ggd_last_message_date, fields.Date.today())

        # Step 3: Verify idempotency - re-claim same key returns False.
        # Finalizing revoked approval, so this also proves the duplicate check
        # runs before the approval check: an already-sent key must report
        # False, not "not approved".
        can_resend = lead.ggd_claim_send_key(key)
        self.assertFalse(can_resend)

    # ------------------------------------------------------------------
    # Atomic claim: the guard the live n8n workflow actually reaches
    #
    # The deployed "Claim send key before SMTP" node does NOT call
    # ggd_claim_send_key(). It performs an ordinary Odoo record update. These
    # tests therefore exercise the plain write() path as well as the method,
    # because the plain path is the one that has to fail closed in production.
    #
    # The workflow decides whether a send is allowed from a snapshot taken
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
        """The only valid key shape: opportunity ID plus approved draft version."""
        return "%s:%s" % (lead.id, lead.ggd_approved_draft_version)

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

    def test_contact_basis_cleared_after_approval_still_sends(self):
        """Clearing the basis after approval no longer stops the claim.

        It used to: the claim re-read the basis under the row lock. That
        blocker was removed with the approval-time check, so the two cannot
        disagree and an approved lead cannot stall at the claim.
        """
        lead = self._approved_lead()
        lead.write({"ggd_contact_basis": False})
        self.assertTrue(lead.ggd_outreach_approved)
        self.assertTrue(lead.ggd_claim_send_key(self._key(lead)))
        self.assertEqual(lead.ggd_last_send_key, self._key(lead))

    def test_missing_contact_basis_no_longer_blocks_the_claim(self):
        lead = self._approved_lead()
        lead.write({"ggd_contact_basis": False})
        lead.write({"ggd_last_send_key": self._key(lead)})
        self.assertEqual(lead.ggd_last_send_key, self._key(lead))

    def test_thin_contact_basis_note_no_longer_blocks_the_claim(self):
        lead = self._approved_lead()
        lead.write({"ggd_contact_basis_note": "ok"})
        lead.write({"ggd_last_send_key": self._key(lead)})
        self.assertEqual(lead.ggd_last_send_key, self._key(lead))

    def test_blocked_claim_message_does_not_leak_stored_values(self):
        """Reasons cross the RPC boundary into n8n logs; row contents must not."""
        lead = self._approved_lead(
            ggd_contact_basis_note="Opt-in ref SECRET-EVIDENCE-1183 on file.",
            email_from="secret-recipient@ggd-qa.invalid",
        )
        # Suppression, not a missing basis, is what blocks a claim now.
        lead.write({"ggd_do_not_contact": True})

        with self.assertRaises(ValidationError) as caught:
            lead.write({"ggd_last_send_key": self._key(lead)})

        message = str(caught.exception)
        self.assertNotIn("SECRET-EVIDENCE-1183", message)
        self.assertNotIn("secret-recipient", message)

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
        """A newly reviewed draft and approval must still be sendable."""
        lead = self._approved_lead()
        first_key = self._key(lead)
        self.assertTrue(lead.ggd_claim_send_key(first_key))
        self._finalize(lead, "<qa-v1@example.invalid>")

        lead.ggd_prepare_draft("Version two subject", "Version two body")
        lead.action_ggd_approve_outreach()
        second_key = self._key(lead)

        self.assertNotEqual(second_key, first_key)
        self.assertTrue(lead.ggd_claim_send_key(second_key))
        self.assertEqual(lead.ggd_last_send_key, second_key)

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

        Each opportunity has its own deterministic key and row lock. A fix
        implemented as a table-wide lock would serialize unrelated sends, so
        the distinction is worth pinning down.
        """
        first = self._approved_lead()
        second = self._approved_lead()
        first_key = self._key(first)
        second_key = self._key(second)

        self.assertTrue(first.ggd_claim_send_key(first_key))
        self.assertTrue(second.ggd_claim_send_key(second_key))
        self.assertFalse(first.ggd_claim_send_key(first_key))

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

    # ------------------------------------------------------------------
    # Complete workflow contract: qualification, reviewed drafts, replies,
    # SMTP audit, bounce handling, and deduplicated follow-up activities.
    # ------------------------------------------------------------------

    def test_approval_no_longer_requires_a_draft_but_sending_still_does(self):
        """Approving is free; sending an email that does not exist is not.

        Kaan's decision, 4 September 2026. The approval is granted with no
        subject, body or version, so no approved draft version is stamped,
        so _ggd_expected_send_key has nothing to build a key from and the
        claim cannot succeed. The idempotency guarantee is what keeps this
        from becoming a way to send empty mail.
        """
        lead = self._lead(
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
            ggd_draft_subject=False,
            ggd_draft_body=False,
            ggd_draft_version=False,
            ggd_draft_status="empty",
        )

        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_approved_draft_version)

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key("%s:anything" % lead.id)
        self.assertFalse(lead.ggd_last_send_key)

    def test_prepare_draft_revokes_old_approval_and_returns_new_version(self):
        lead = self._approved_lead()
        old_version = lead.ggd_draft_version

        result = lead.ggd_prepare_draft("New reviewed subject", "New reviewed body")
        new_version = result["draft_version"]

        self.assertNotEqual(new_version, old_version)
        self.assertEqual(lead.ggd_draft_version, new_version)
        self.assertEqual(lead.ggd_draft_status, "ready")
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_approved_draft_version)

    def test_prepare_draft_returns_a_json_object_not_a_bare_string(self):
        """Defect 13 regression guard.

        n8n's HTTP Request node fails a node whose response body is a
        top-level JSON scalar string, even when Odoo has already committed the
        work. Workflow 2 therefore reported failed runs for drafts it had
        successfully stored. The contract is a dict; asserting the type here
        stops anyone restoring the bare string later without discovering why
        it was changed.
        """
        lead = self._lead(ggd_draft_subject=False, ggd_draft_body=False, ggd_draft_version=False)

        result = lead.ggd_prepare_draft("Reviewed subject", "Reviewed body")

        self.assertIsInstance(result, dict)
        self.assertEqual(set(result), {"draft_version"})
        self.assertEqual(result["draft_version"], lead.ggd_draft_version)
        self.assertTrue(result["draft_version"])

    def test_prepare_draft_records_the_language_it_was_written_in(self):
        """Workflow 5 must follow up in the language of the first email.

        Before this field the follow-up prompt had to guess from a body
        summary, which is how a German first contact acquires an English
        follow-up.
        """
        lead = self._lead(ggd_draft_subject=False, ggd_draft_body=False, ggd_draft_version=False)

        lead.ggd_prepare_draft("Betreff", "Guten Tag, dies ist ein Entwurf.", language="de")

        self.assertEqual(lead.ggd_draft_language, "de")

    def test_prepare_draft_normalises_and_drops_unusable_language_tags(self):
        for supplied, expected in (
            ("DE", "de"),
            ("pt-br", "pt-BR"),
            (" en ", "en"),
            ("Deutsch", False),
            ("", False),
            (None, False),
        ):
            with self.subTest(language=supplied):
                lead = self._lead(
                    ggd_draft_subject=False, ggd_draft_body=False, ggd_draft_version=False
                )
                lead.ggd_prepare_draft("Reviewed subject", "Reviewed body", language=supplied)
                self.assertEqual(lead.ggd_draft_language, expected)

    def test_prepare_draft_stores_the_draft_even_when_the_language_is_junk(self):
        """A bad language tag must never cost us a draft a human could review.

        Same trade as defect 13: failing the whole call over metadata makes the
        workflow report a failure for work worth keeping, and a retry mints a
        second version.
        """
        lead = self._lead(ggd_draft_subject=False, ggd_draft_body=False, ggd_draft_version=False)

        result = lead.ggd_prepare_draft("Reviewed subject", "Reviewed body", language="not a tag")

        self.assertTrue(result["draft_version"])
        self.assertEqual(lead.ggd_draft_status, "ready")
        self.assertEqual(lead.ggd_draft_body, "Reviewed body")
        self.assertFalse(lead.ggd_draft_language)

    def test_editing_the_draft_language_does_not_revoke_an_approval(self):
        """The language is a record, not part of the approved content.

        ggd_draft_language is deliberately outside GGD_DRAFT_FIELDS. If it ever
        moves inside, this test fails and whoever moved it has to explain why
        correcting a language code should invalidate a human's approval.
        """
        lead = self._approved_lead()

        lead.write({"ggd_draft_language": "de"})

        self.assertTrue(lead.ggd_outreach_approved)
        self.assertEqual(lead.ggd_approved_draft_version, lead.ggd_draft_version)

    def test_direct_draft_edit_revokes_approval(self):
        lead = self._approved_lead()

        lead.write({"ggd_draft_subject": "Edited after approval"})

        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_approved_draft_version)
        self.assertEqual(lead.ggd_draft_status, "ready")

    def test_clearing_a_draft_returns_the_lead_to_empty(self):
        """Removing a draft must not leave the record claiming to be ready.

        write() forces ggd_draft_status to "ready" for any draft change, which
        is correct for an edit. Applied to a clear it produced status "ready"
        with no version: a lead that looks draft-ready with nothing to approve.
        """
        lead = self._lead()

        lead.write(
            {
                "ggd_draft_subject": False,
                "ggd_draft_body": False,
                "ggd_draft_version": False,
            }
        )

        self.assertEqual(lead.ggd_draft_status, "empty")
        self.assertFalse(lead.ggd_draft_version)
        self.assertFalse(lead.ggd_draft_subject)
        self.assertFalse(lead.ggd_draft_body)

    def test_clearing_a_draft_still_revokes_approval(self):
        lead = self._approved_lead()

        lead.write({"ggd_draft_subject": False, "ggd_draft_body": False})

        self.assertEqual(lead.ggd_draft_status, "empty")
        self.assertFalse(lead.ggd_draft_version)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_approved_draft_version)
        self.assertFalse(lead.ggd_approved_recipient)
        self.assertFalse(lead.ggd_outreach_approved_by)

    def test_whitespace_only_draft_values_count_as_a_clear(self):
        lead = self._lead()

        lead.write({"ggd_draft_subject": "   ", "ggd_draft_body": "\n  \n"})

        self.assertEqual(lead.ggd_draft_status, "empty")
        self.assertFalse(lead.ggd_draft_version)

    def test_emptying_only_the_subject_is_an_edit_not_a_clear(self):
        """A partial write is an edit, because the body still holds content."""
        lead = self._lead()
        original_version = lead.ggd_draft_version

        lead.write({"ggd_draft_subject": False})

        self.assertEqual(lead.ggd_draft_status, "ready")
        self.assertTrue(lead.ggd_draft_version)
        self.assertNotEqual(lead.ggd_draft_version, original_version)
        self.assertEqual(lead.ggd_draft_body, VALID_DRAFT_BODY)

    def test_clearing_a_draft_on_two_leads_at_once_clears_both(self):
        first = self._lead()
        second = self._lead(email_from="control-test-2@ggd-qa.invalid")

        (first | second).write(
            {"ggd_draft_subject": False, "ggd_draft_body": False}
        )

        for lead in (first, second):
            self.assertEqual(lead.ggd_draft_status, "empty")
            self.assertFalse(lead.ggd_draft_version)

    def test_claim_does_not_mark_smtp_confirmation(self):
        lead = self._approved_lead()

        lead.ggd_claim_send_key(self._key(lead))

        self.assertTrue(lead.ggd_last_sent_at)
        self.assertFalse(lead.ggd_send_confirmed_at)
        self.assertEqual(lead.ggd_delivery_status, "claimed")

    def test_finalize_send_records_complete_smtp_audit(self):
        lead = self._claimed_lead()

        self.assertTrue(
            lead.ggd_finalize_send(
                "<qa-message-1@example.invalid>",
                lead.email_from,
                lead.ggd_draft_subject,
                "Fictional reviewed body summary.",
            )
        )

        self.assertTrue(lead.ggd_send_confirmed_at)
        self.assertEqual(lead.ggd_delivery_status, "accepted")
        self.assertEqual(lead.ggd_last_message_id, "<qa-message-1@example.invalid>")
        self.assertEqual(lead.ggd_last_sent_recipient, lead.email_from)
        self.assertEqual(lead.ggd_last_sent_subject, VALID_DRAFT_SUBJECT)
        self.assertEqual(lead.ggd_last_sent_draft_version, VALID_DRAFT_VERSION)
        self.assertEqual(lead.ggd_draft_status, "sent")

    def test_finalize_send_refuses_mismatched_subject(self):
        lead = self._claimed_lead()

        with self.assertRaises(ValidationError):
            lead.ggd_finalize_send(
                "<qa-message-2@example.invalid>",
                lead.email_from,
                "A subject nobody approved",
                "Fictional body summary.",
            )

        self.assertFalse(lead.ggd_send_confirmed_at)

    def test_finalize_send_is_idempotent(self):
        lead = self._claimed_lead()
        args = (
            "<qa-message-3@example.invalid>",
            lead.email_from,
            lead.ggd_draft_subject,
            "Fictional body summary.",
        )

        self.assertTrue(lead.ggd_finalize_send(*args))
        message_count = len(
            lead.message_ids.filtered(
                lambda message: "GGD outreach accepted by SMTP" in (message.body or "")
            )
        )
        self.assertFalse(lead.ggd_finalize_send(*args))
        self.assertEqual(
            len(
                lead.message_ids.filtered(
                    lambda message: "GGD outreach accepted by SMTP"
                    in (message.body or "")
                )
            ),
            message_count,
        )

    def test_second_approved_draft_can_be_finalized(self):
        lead = self._claimed_lead()
        first_key = lead.ggd_last_send_key
        self._finalize(lead, "<qa-v1-final@example.invalid>")

        lead.ggd_prepare_draft("Version two reviewed subject", "Version two reviewed body")
        lead.action_ggd_approve_outreach()
        second_key = self._key(lead)
        self.assertNotEqual(second_key, first_key)
        self.assertTrue(lead.ggd_claim_send_key(second_key))
        self.assertTrue(self._finalize(lead, "<qa-v2-final@example.invalid>"))

        self.assertEqual(lead.ggd_last_confirmed_send_key, second_key)
        self.assertEqual(lead.ggd_last_message_id, "<qa-v2-final@example.invalid>")

    def test_sent_draft_can_be_approved_again_but_not_sent_again(self):
        """Re-approving an already-sent draft is now allowed.

        The approval-time guard against it went with the other prerequisites.
        What stops a second send is the claim: the same send key was already
        used, so ggd_claim_send_key reports it as already sent rather than
        issuing a fresh claim. That is the duplicate-send protection now.
        """
        lead = self._claimed_lead()
        self._finalize(lead, "<qa-already-sent@example.invalid>")

        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)

        self.assertFalse(lead.ggd_claim_send_key(self._key(lead)))

    def test_unresolved_claim_blocks_a_new_draft(self):
        lead = self._claimed_lead()

        with self.assertRaises(ValidationError):
            lead.ggd_prepare_draft("Unsafe replacement", "Unsafe replacement body")

        self.assertTrue(lead.ggd_outreach_approved)
        self.assertEqual(lead.ggd_delivery_status, "claimed")

    def test_unresolved_claim_blocks_a_direct_draft_edit(self):
        lead = self._claimed_lead()
        original_subject = lead.ggd_draft_subject
        original_version = lead.ggd_draft_version

        with self.assertRaises(ValidationError):
            lead.write({"ggd_draft_subject": "Unsafe direct edit"})

        self.assertEqual(lead.ggd_draft_subject, original_subject)
        self.assertEqual(lead.ggd_draft_version, original_version)
        self.assertTrue(lead.ggd_outreach_approved)

    def test_failed_claim_release_allows_the_approved_draft_to_be_reclaimed(self):
        lead = self._claimed_lead()
        key = lead.ggd_last_send_key
        lead.ggd_record_automation_error(
            "SMTP failed before accepting the fictional message.", True
        )

        self.assertTrue(lead.action_ggd_release_failed_send_claim())

        self.assertFalse(lead.ggd_last_send_key)
        self.assertFalse(lead.ggd_last_sent_at)
        self.assertEqual(lead.ggd_delivery_status, "none")
        self.assertTrue(lead.ggd_last_claim_released_at)
        self.assertEqual(lead.ggd_last_claim_released_by, self.env.user)
        self.assertTrue(lead.ggd_claim_send_key(key))

    def test_confirmed_send_claim_cannot_be_released(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<qa-confirmed@example.invalid>")

        with self.assertRaises(ValidationError):
            lead.action_ggd_release_failed_send_claim()

    def test_released_claim_cannot_be_finalized(self):
        lead = self._claimed_lead()
        recipient = lead.ggd_claimed_recipient
        subject = lead.ggd_draft_subject
        lead.action_ggd_release_failed_send_claim()

        with self.assertRaises(ValidationError):
            lead.ggd_finalize_send(
                "<released-claim@example.invalid>",
                recipient,
                subject,
                "Fictional reviewed body summary.",
            )

    def test_qualification_low_confidence_routes_to_review(self):
        lead = self._lead()

        accepted = lead.ggd_apply_qualification(
            72,
            "Good fictional fit with missing detail.",
            "Lead with the documented capability gap.",
            0.55,
            "https://example.invalid/research",
        )

        self.assertFalse(accepted)
        self.assertEqual(lead.ggd_qualification_state, "review")
        self.assertTrue(lead.ggd_automation_needs_review)
        self.assertFalse(lead.ggd_outreach_approved)

    def test_qualification_high_confidence_becomes_ready(self):
        lead = self._lead()

        accepted = lead.ggd_apply_qualification(
            88,
            "Strong fictional fit with a documented source.",
            "Use the fictional market-entry angle.",
            0.91,
            industry="Industrial software",
            product_focus="Fictional planning platform",
            recommended_buyer_roles=["Managing Director", "Operations Lead"],
        )

        self.assertTrue(accepted)
        self.assertEqual(lead.ggd_qualification_state, "ready")
        self.assertFalse(lead.ggd_automation_needs_review)
        self.assertEqual(lead.ggd_industry, "Industrial software")
        self.assertIn("Operations Lead", lead.ggd_recommended_buyer_roles)

    def test_unsubscribe_reply_suppresses_and_records_response_state(self):
        lead = self._approved_lead()

        lead.ggd_record_reply(
            "unsubscribe",
            "The fictional contact asked to stop.",
            "Do not contact again.",
            0.98,
            reply_message_id="<reply-1@example.invalid>",
        )

        self.assertTrue(lead.ggd_do_not_contact)
        self.assertFalse(lead.ggd_outreach_approved)
        self.assertEqual(lead.ggd_reply_category, "unsubscribe")
        self.assertTrue(lead.ggd_last_reply_received_at)

    def test_low_confidence_reply_routes_to_review(self):
        lead = self._lead()

        accepted = lead.ggd_record_reply(
            "unclear",
            "The fictional reply could not be classified.",
            "Review the original message manually.",
            0.42,
            response_draft="No automatic response should be sent.",
        )

        self.assertFalse(accepted)
        self.assertTrue(lead.ggd_automation_needs_review)
        self.assertEqual(lead.ggd_response_draft, "No automatic response should be sent.")

    def test_reply_accepts_iso_8601_workflow_timestamps(self):
        lead = self._lead()

        lead.ggd_record_reply(
            "interested",
            "The fictional contact asked for more information.",
            "Prepare a manual response.",
            0.95,
            received_at="2026-08-21T10:15:30Z",
            suggested_follow_up_at="2026-08-22T12:30:00+02:00",
        )

        self.assertEqual(
            fields.Datetime.to_string(lead.ggd_last_reply_received_at),
            "2026-08-21 10:15:30",
        )
        self.assertEqual(
            fields.Datetime.to_string(lead.ggd_suggested_follow_up_at),
            "2026-08-22 10:30:00",
        )

    def test_bounce_without_a_matching_confirmed_send_is_refused(self):
        lead = self._lead()

        with self.assertRaises(ValidationError):
            lead.ggd_record_bounce(
                "<unknown@example.invalid>",
                "No confirmed fictional outbound message exists.",
                True,
            )

        self.assertFalse(lead.ggd_do_not_contact)

    def test_qualification_cannot_clear_delivery_review(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<qa-review@example.invalid>")
        lead.ggd_record_bounce(
            "<qa-review@example.invalid>", "Temporary delivery problem.", False
        )

        lead.ggd_apply_qualification(
            90,
            "Strong fictional fit.",
            "Use the reviewed fictional angle.",
            0.95,
        )

        self.assertFalse(lead.ggd_qualification_needs_review)
        self.assertTrue(lead.ggd_delivery_needs_review)
        self.assertTrue(lead.ggd_automation_needs_review)

    def test_hard_bounce_marks_delivery_and_suppresses(self):
        lead = self._claimed_lead()
        lead.ggd_finalize_send(
            "<qa-message-4@example.invalid>",
            lead.email_from,
            lead.ggd_draft_subject,
            "Fictional body summary.",
        )

        lead.ggd_record_bounce(
            "<qa-message-4@example.invalid>",
            "Mailbox does not exist.",
            True,
        )

        self.assertEqual(lead.ggd_delivery_status, "bounced")
        self.assertTrue(lead.ggd_do_not_contact)
        self.assertTrue(lead.ggd_automation_needs_review)

    def test_reply_candidate_match_prefers_outbound_message_id(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<qa-match@example.invalid>")

        result = self.Lead.ggd_find_reply_candidates(
            "<qa-match@example.invalid>", "different@example.invalid"
        )

        self.assertEqual(result["match_type"], "message_id")
        self.assertEqual([candidate["id"] for candidate in result["candidates"]], [lead.id])

    def test_reply_candidate_match_falls_back_to_sender(self):
        lead = self._lead(
            email_from="Fictional Sender <sender-fallback@ggd-qa.invalid>"
        )

        result = self.Lead.ggd_find_reply_candidates(
            "<missing@example.invalid>", "SENDER-FALLBACK@ggd-qa.invalid"
        )

        self.assertEqual(result["match_type"], "sender")
        self.assertEqual([candidate["id"] for candidate in result["candidates"]], [lead.id])

    def test_automation_error_marks_work_for_review(self):
        lead = self._lead()

        lead.ggd_record_automation_error(
            "Workflow 3 stopped after its send claim; check sent mail.", True
        )

        self.assertTrue(lead.ggd_workflow_needs_review)
        self.assertTrue(lead.ggd_delivery_needs_review)
        self.assertTrue(lead.ggd_automation_needs_review)

    def test_follow_up_queue_is_deduplicated_per_confirmed_send(self):
        lead = self._claimed_lead()
        lead.ggd_finalize_send(
            "<qa-message-5@example.invalid>",
            lead.email_from,
            lead.ggd_draft_subject,
            "Fictional body summary.",
        )
        self._make_follow_up_due(lead)

        self.assertTrue(lead.ggd_queue_follow_up("A fictional manual follow-up draft."))
        activity_count = len(lead.activity_ids)
        self.assertFalse(lead.ggd_queue_follow_up("A duplicate draft must not create work."))
        self.assertEqual(len(lead.activity_ids), activity_count)
        self.assertTrue(lead.ggd_last_follow_up_queued_at)

    def test_follow_up_queue_refuses_a_lead_with_a_reply(self):
        lead = self._claimed_lead()
        lead.ggd_finalize_send(
            "<qa-message-6@example.invalid>",
            lead.email_from,
            lead.ggd_draft_subject,
            "Fictional body summary.",
        )
        self._make_follow_up_due(lead)
        lead.ggd_record_reply(
            "interested",
            "The fictional contact replied after the send.",
            "Schedule a fictional meeting.",
            0.95,
        )

        with self.assertRaises(ValidationError):
            lead.ggd_queue_follow_up("This follow-up must not be queued.")

    def test_follow_up_queue_refuses_a_recent_send(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<qa-recent@example.invalid>")

        with self.assertRaises(ValidationError):
            lead.ggd_queue_follow_up("This follow-up is too early.")

    def test_approval_no_longer_requires_a_recipient_but_sending_does(self):
        """A lead with no address can be approved; it can never be claimed."""
        lead = self._lead(
            email_from=False,
            ggd_contact_basis="consent",
            ggd_contact_basis_note=VALID_NOTE,
        )

        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)

        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(self._key(lead))
        self.assertFalse(lead.ggd_last_send_key)

    def test_recipient_change_revokes_approval(self):
        lead = self._approved_lead()

        lead.write({"email_from": "replacement@ggd-qa.invalid"})

        self.assertFalse(lead.ggd_outreach_approved)
        self.assertFalse(lead.ggd_approved_draft_version)
        self.assertEqual(lead.ggd_draft_status, "ready")

    def test_unresolved_claim_blocks_recipient_change(self):
        lead = self._claimed_lead()

        with self.assertRaises(ValidationError):
            lead.write({"email_from": "unsafe-change@ggd-qa.invalid"})

    def test_linked_contact_email_change_invalidates_claim(self):
        partner = self.env["res.partner"].create(
            {"name": "Fictional approved contact", "email": "approved@ggd-qa.invalid"}
        )
        lead = self._approved_lead(
            partner_id=partner.id,
            email_from="approved@ggd-qa.invalid",
        )
        approved_recipient = lead.ggd_approved_recipient

        partner.email = "changed-by-contact@ggd-qa.invalid"
        lead.invalidate_recordset(["email_from"])

        self.assertEqual(approved_recipient, "approved@ggd-qa.invalid")
        self.assertEqual(lead.email_from, "changed-by-contact@ggd-qa.invalid")
        with self.assertRaises(ValidationError):
            lead.ggd_claim_send_key(self._key(lead))

    def test_revocation_during_smtp_keeps_claim_auditable(self):
        lead = self._claimed_lead()
        claimed_version = lead.ggd_claimed_draft_version
        lead.action_ggd_revoke_outreach()

        self.assertTrue(
            lead.ggd_finalize_send(
                "<revoked-in-flight@example.invalid>",
                "control-test@ggd-qa.invalid",
                lead.ggd_draft_subject,
                "Fictional reviewed body summary.",
            )
        )

        self.assertEqual(lead.ggd_last_sent_draft_version, claimed_version)
        self.assertEqual(lead.ggd_last_sent_recipient, "control-test@ggd-qa.invalid")
        self.assertFalse(lead.ggd_claimed_recipient)

    def test_suppression_during_smtp_keeps_claim_auditable(self):
        lead = self._claimed_lead()
        lead.write({"ggd_do_not_contact": True})

        self.assertTrue(
            lead.ggd_finalize_send(
                "<suppressed-in-flight@example.invalid>",
                "control-test@ggd-qa.invalid",
                lead.ggd_draft_subject,
                "Fictional reviewed body summary.",
            )
        )

        self.assertTrue(lead.ggd_do_not_contact)
        self.assertEqual(lead.ggd_delivery_status, "accepted")

    def test_archived_lead_can_match_reply_by_message_id(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<archived-match@example.invalid>")
        lead.active = False

        result = self.Lead.ggd_find_reply_candidates(
            "<archived-match@example.invalid>", False
        )

        self.assertEqual([candidate["id"] for candidate in result["candidates"]], [lead.id])

    def test_archived_lead_can_match_reply_by_sender(self):
        lead = self._lead(email_from="archived-sender@ggd-qa.invalid")
        lead.active = False

        result = self.Lead.ggd_find_reply_candidates(
            False, "archived-sender@ggd-qa.invalid"
        )

        self.assertEqual([candidate["id"] for candidate in result["candidates"]], [lead.id])

    def test_human_can_resolve_all_automation_review_flags(self):
        lead = self._lead()
        lead.ggd_record_automation_error("Fictional workflow failure.", True)

        self.assertTrue(lead.action_ggd_resolve_automation_review())

        self.assertFalse(lead.ggd_automation_needs_review)
        self.assertFalse(lead.ggd_workflow_needs_review)
        self.assertFalse(lead.ggd_delivery_needs_review)
        self.assertFalse(lead.ggd_automation_review_summary)

    def test_failed_claim_release_preserves_review_until_human_resolution(self):
        lead = self._claimed_lead()
        lead.ggd_record_automation_error("Fictional uncertain SMTP result.", True)

        lead.action_ggd_release_failed_send_claim()

        self.assertTrue(lead.ggd_workflow_needs_review)
        self.assertTrue(lead.ggd_delivery_needs_review)
        self.assertTrue(lead.ggd_automation_needs_review)

    def test_suppressed_reply_does_not_store_outbound_draft(self):
        lead = self._lead(ggd_do_not_contact=True)

        lead.ggd_record_reply(
            "information",
            "The fictional suppressed contact replied.",
            "Send more information.",
            0.95,
            response_draft="This outbound draft must not be stored.",
            reply_message_id="<suppressed-reply@example.invalid>",
        )

        self.assertFalse(lead.ggd_response_draft)
        self.assertFalse(lead.ggd_suggested_follow_up_at)
        self.assertIn("suppressed", lead.ggd_suggested_next_action)

    def test_duplicate_reply_message_id_is_idempotent(self):
        lead = self._lead()
        first_received = "2026-08-21T10:00:00Z"
        lead.ggd_record_reply(
            "interested",
            "First fictional reply.",
            "Review the reply.",
            0.9,
            reply_message_id="<duplicate-reply@example.invalid>",
            received_at=first_received,
        )

        accepted = lead.ggd_record_reply(
            "objection",
            "Duplicate delivery must not replace the first analysis.",
            "Do something different.",
            0.9,
            reply_message_id="<duplicate-reply@example.invalid>",
            received_at="2026-08-21T10:01:00Z",
        )

        self.assertFalse(accepted)
        self.assertEqual(lead.ggd_reply_category, "interested")
        self.assertEqual(lead.ggd_reply_summary, "First fictional reply.")

    def test_older_reply_does_not_replace_latest_reply_state(self):
        lead = self._lead()
        lead.ggd_record_reply(
            "meeting",
            "Newest fictional reply.",
            "Review meeting request.",
            0.9,
            reply_message_id="<newest-reply@example.invalid>",
            received_at="2026-08-21T12:00:00Z",
        )

        accepted = lead.ggd_record_reply(
            "objection",
            "Older fictional reply.",
            "This must not replace the latest action.",
            0.9,
            reply_message_id="<older-reply@example.invalid>",
            received_at="2026-08-21T11:00:00Z",
        )

        self.assertFalse(accepted)
        self.assertEqual(lead.ggd_reply_category, "meeting")
        self.assertEqual(lead.ggd_last_reply_message_id, "<newest-reply@example.invalid>")

    def test_unmatched_inbound_creates_one_deduplicated_review_record(self):
        before = self.Lead.with_context(active_test=False).search_count([])
        first_id = self.Lead.ggd_queue_unmatched_inbound(
            "<unmatched@example.invalid>",
            "Fictional Sender <unmatched-sender@ggd-qa.invalid>",
            "Fictional unmatched message",
            "No unambiguous opportunity candidate exists.",
            "2026-08-21T13:00:00Z",
        )
        second_id = self.Lead.ggd_queue_unmatched_inbound(
            "<unmatched@example.invalid>",
            "unmatched-sender@ggd-qa.invalid",
            "Fictional unmatched message",
            "No unambiguous opportunity candidate exists.",
            "2026-08-21T13:00:00Z",
        )

        review = self.Lead.browse(first_id)
        self.assertEqual(first_id, second_id)
        self.assertEqual(
            self.Lead.with_context(active_test=False).search_count([]), before + 1
        )
        self.assertTrue(review.ggd_reply_needs_review)
        self.assertTrue(review.activity_ids)

    def test_follow_up_queue_refuses_nonaccepted_delivery(self):
        lead = self._claimed_lead()
        self._finalize(lead, "<bounced-follow-up@example.invalid>")
        self._make_follow_up_due(lead)
        lead.ggd_record_bounce(
            "<bounced-follow-up@example.invalid>", "Fictional hard bounce.", True
        )
        lead.action_ggd_resolve_automation_review()

        with self.assertRaises(ValidationError):
            lead.ggd_queue_follow_up("This bounce must never receive a follow-up.")


@tagged("post_install", "-at_install")
class TestGgdApproverGroup(TransactionCase):
    """Only the approver group may approve outreach or clear Do not contact.

    The rest of this module runs as the superuser, which is exempt from the
    check the way it is exempt from every access rule. These tests act as
    two ordinary internal users: a salesperson with full CRM rights and the
    same profile plus the approver group. The first is the shape of the
    automation user n8n runs as.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env["crm.lead"]
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        crm_groups = [
            cls.env.ref("base.group_user").id,
            cls.env.ref("sales_team.group_sale_salesman_all_leads").id,
        ]
        cls.salesperson = Users.create(
            {
                "name": "GGD automation-shaped user",
                "login": "ggd-automation-shaped@ggd-qa.invalid",
                "group_ids": [(6, 0, crm_groups)],
            }
        )
        cls.approver = Users.create(
            {
                "name": "GGD approver",
                "login": "ggd-approver@ggd-qa.invalid",
                "group_ids": [
                    (6, 0, crm_groups + [cls.env.ref(cls.Lead.GGD_APPROVER_GROUP).id])
                ],
            }
        )

    def _lead(self, **values):
        base = {
            "name": "QA approver fixture",
            "email_from": "approver-test@ggd-qa.invalid",
            "ggd_draft_subject": VALID_DRAFT_SUBJECT,
            "ggd_draft_body": VALID_DRAFT_BODY,
            "ggd_draft_version": VALID_DRAFT_VERSION,
            "ggd_draft_status": "ready",
            "ggd_contact_basis": "consent",
            "ggd_contact_basis_note": VALID_NOTE,
        }
        base.update(values)
        return self.Lead.create(base)

    def test_admin_is_an_approver_after_install(self):
        """The upgrade must not lock the owner out of the approve button."""
        self.assertTrue(
            self.env.ref("base.user_admin").has_group(self.Lead.GGD_APPROVER_GROUP)
        )

    def test_salesperson_cannot_approve_by_button(self):
        lead = self._lead().with_user(self.salesperson)
        with self.assertRaises(AccessError):
            lead.action_ggd_approve_outreach()
        self.assertFalse(lead.ggd_outreach_approved)

    def test_salesperson_cannot_approve_by_write(self):
        """The automation user's route is a plain write; it must fail too."""
        lead = self._lead().with_user(self.salesperson)
        with self.assertRaises(AccessError):
            lead.write({"ggd_outreach_approved": True})
        self.assertFalse(lead.ggd_outreach_approved)

    def test_salesperson_cannot_create_an_approved_lead(self):
        with self.assertRaises(AccessError):
            self.Lead.with_user(self.salesperson).create(
                {
                    "name": "Born approved",
                    "email_from": "born-approved@ggd-qa.invalid",
                    "ggd_draft_subject": VALID_DRAFT_SUBJECT,
                    "ggd_draft_body": VALID_DRAFT_BODY,
                    "ggd_contact_basis": "consent",
                    "ggd_contact_basis_note": VALID_NOTE,
                    "ggd_outreach_approved": True,
                }
            )

    def test_salesperson_can_suppress_but_not_unsuppress(self):
        """Unsubscribe handling stays open; re-opening a person does not."""
        lead = self._lead().with_user(self.salesperson)
        lead.write({"ggd_do_not_contact": True})
        self.assertTrue(lead.ggd_do_not_contact)
        with self.assertRaises(AccessError):
            lead.write({"ggd_do_not_contact": False})
        self.assertTrue(lead.ggd_do_not_contact)

    def test_salesperson_may_still_write_other_fields(self):
        """The check must not bleed into ordinary CRM edits."""
        lead = self._lead().with_user(self.salesperson)
        lead.write({"ggd_fit_score": 77, "ggd_industry": "Packaging"})
        self.assertEqual(lead.ggd_fit_score, 77)

    def test_approver_can_approve_and_unsuppress(self):
        lead = self._lead().with_user(self.approver)
        lead.action_ggd_approve_outreach()
        self.assertTrue(lead.ggd_outreach_approved)
        self.assertEqual(lead.ggd_outreach_approved_by, self.approver)
        lead.write({"ggd_do_not_contact": True})
        self.assertFalse(lead.ggd_outreach_approved)
        lead.write({"ggd_do_not_contact": False})
        self.assertFalse(lead.ggd_do_not_contact)

    def test_approve_button_is_hidden_from_non_approvers(self):
        """The form's Approve button carries the group, so the UI matches."""
        view = self.env.ref("ggd_crm.crm_lead_view_form_ggd")
        self.assertIn(
            'groups="ggd_crm.group_ggd_outreach_approver"',
            view.arch_db,
        )


@tagged("post_install", "-at_install")
class TestGgdDailySendCap(TransactionCase):
    """The claim refuses once the trailing-24-hour claim count reaches the cap."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env["crm.lead"]
        cls.Params = cls.env["ir.config_parameter"].sudo()

    def setUp(self):
        super().setUp()
        # The cap counts every lead in the database, not only this class's
        # fixtures, so any real send claimed in the trailing 24 hours makes
        # these tests start from a non-zero count and the arithmetic below
        # stops holding. Clearing the window here keeps the suite reproducible
        # whatever the stack has been doing; TransactionCase rolls the
        # statement back, so live records are not modified.
        self.env.cr.execute(
            "UPDATE crm_lead SET ggd_last_sent_at = NULL "
            "WHERE ggd_last_sent_at >= %s",
            (fields.Datetime.now() - timedelta(hours=24),),
        )
        self.Lead.invalidate_model(["ggd_last_sent_at"])

    def _set_cap(self, value):
        self.Params.set_param(self.Lead.GGD_DAILY_SEND_CAP_PARAM, value)

    def _approved_lead(self, n):
        lead = self.Lead.create(
            {
                "name": "QA cap fixture %s" % n,
                "email_from": "cap-%s@ggd-qa.invalid" % n,
                "ggd_draft_subject": VALID_DRAFT_SUBJECT,
                "ggd_draft_body": VALID_DRAFT_BODY,
                "ggd_draft_version": "cap-draft-%s" % n,
                "ggd_draft_status": "ready",
                "ggd_contact_basis": "consent",
                "ggd_contact_basis_note": VALID_NOTE,
            }
        )
        lead.action_ggd_approve_outreach()
        return lead

    @staticmethod
    def _key(lead):
        return "%s:%s" % (lead.id, lead.ggd_approved_draft_version)

    def test_parameter_is_installed_with_a_default(self):
        self.assertEqual(
            int(self.Params.get_param(self.Lead.GGD_DAILY_SEND_CAP_PARAM)),
            self.Lead.GGD_DAILY_SEND_CAP_DEFAULT,
        )

    def test_cap_refuses_the_claim_that_would_exceed_it(self):
        self._set_cap("2")
        first, second, third = (self._approved_lead(i) for i in range(3))
        self.assertTrue(first.ggd_claim_send_key(self._key(first)))
        self.assertTrue(second.ggd_claim_send_key(self._key(second)))
        with self.assertRaisesRegex(ValidationError, "daily send cap"):
            third.ggd_claim_send_key(self._key(third))
        self.assertFalse(third.ggd_last_send_key)
        self.assertTrue(third.ggd_outreach_approved)

    def test_cap_of_zero_stops_all_sending(self):
        self._set_cap("0")
        lead = self._approved_lead(0)
        with self.assertRaisesRegex(ValidationError, "daily send cap"):
            lead.ggd_claim_send_key(self._key(lead))

    def test_missing_parameter_falls_back_to_the_default(self):
        """set_param('') deletes the parameter; that is 'unset', not 'bad'."""
        self._set_cap("")
        self.assertFalse(self.Params.get_param(self.Lead.GGD_DAILY_SEND_CAP_PARAM))
        self.assertEqual(self.Lead._ggd_daily_send_cap(), self.Lead.GGD_DAILY_SEND_CAP_DEFAULT)

    def test_unreadable_cap_fails_closed(self):
        lead = self._approved_lead(0)
        for bad in ("twenty", "-1", "1.5"):
            with self.subTest(value=bad):
                self._set_cap(bad)
                with self.assertRaises(ValidationError):
                    lead.ggd_claim_send_key(self._key(lead))
                self.assertFalse(lead.ggd_last_send_key)

    def test_claims_older_than_24_hours_do_not_count(self):
        self._set_cap("1")
        old, new = self._approved_lead(1), self._approved_lead(2)
        self.assertTrue(old.ggd_claim_send_key(self._key(old)))
        old.flush_recordset(["ggd_last_sent_at"])
        self.env.cr.execute(
            "UPDATE crm_lead SET ggd_last_sent_at = %s WHERE id = %s",
            (datetime.now() - timedelta(hours=25), old.id),
        )
        old.invalidate_recordset(["ggd_last_sent_at"])
        self.assertTrue(new.ggd_claim_send_key(self._key(new)))

    def test_duplicate_claim_of_the_same_key_is_still_false_not_capped(self):
        """Idempotency must win over the cap: a repeat run reports 'already
        sent', it does not get a cap error that n8n would treat as 'blocked'."""
        self._set_cap("1")
        lead = self._approved_lead(1)
        self.assertTrue(lead.ggd_claim_send_key(self._key(lead)))
        self.assertFalse(lead.ggd_claim_send_key(self._key(lead)))


@tagged("post_install", "-at_install")
class TestGgdAutomatedMailSuppression(TransactionCase):
    """Leads the mail gateway makes from machine mail arrive suppressed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env["crm.lead"]

    def _incoming(self, sender, subject="Inbound"):
        return self.Lead.message_new(
            {
                "email_from": sender,
                "subject": subject,
                "message_id": "<gw-%s@ggd-qa.invalid>" % abs(hash(sender)),
            },
            {"name": subject, "type": "opportunity"},
        )

    def test_dmarc_report_arrives_suppressed(self):
        """The exact sender that reached the pipeline on 2 and 4 September."""
        lead = self._incoming(
            "noreply-dmarc-support@google.com",
            "Report domain: germanygrowthdesk.com Submitter: google.com",
        )
        self.assertTrue(lead.ggd_do_not_contact)
        self.assertTrue(lead.ggd_automation_needs_review)

    def test_machine_senders_are_suppressed(self):
        for sender in (
            "mailer-daemon@example.com",
            "postmaster@example.com",
            "no-reply@vendor.example",
            "noreply@vendor.example",
            "do-not-reply@vendor.example",
            "bounces@vendor.example",
            "abuse@vendor.example",
        ):
            with self.subTest(sender=sender):
                self.assertTrue(self._incoming(sender).ggd_do_not_contact)

    def test_a_real_enquiry_is_untouched(self):
        """The alias must still take ordinary inbound mail normally."""
        lead = self._incoming("buyer@fictional-prospect.invalid", "Quote request")
        self.assertFalse(lead.ggd_do_not_contact)
        self.assertFalse(lead.ggd_automation_needs_review)

    def test_a_suppressed_lead_cannot_be_approved(self):
        lead = self._incoming("noreply-dmarc-support@google.com")
        lead.write(
            {
                "ggd_contact_basis": "other",
                "ggd_contact_basis_note": VALID_NOTE,
                "ggd_draft_subject": VALID_DRAFT_SUBJECT,
                "ggd_draft_body": VALID_DRAFT_BODY,
                "ggd_draft_version": VALID_DRAFT_VERSION,
            }
        )
        # Filling in the basis is exactly what the old validation error
        # invited; it must no longer be enough to unlock the send path.
        with self.assertRaises(ValidationError):
            lead.action_ggd_approve_outreach()
        self.assertFalse(lead.ggd_outreach_approved)
