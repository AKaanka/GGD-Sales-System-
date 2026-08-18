"""Control tests for the GGD outreach approval gate.

These cover the non-negotiable rules in PLAN.md and the contact-basis
enforcement described in docs/LAWFUL-CONTACT-PROCEDURE.md section 8. The point
of the suite is that the gate is verified rather than assumed: it must hold
through the approval button, through a direct write, and through create.

Run:
    docker compose exec odoo odoo -d ggd --test-enable \\
        --test-tags /ggd_crm --stop-after-init -u ggd_crm
"""

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

    # ------------------------------------------------------------------
    # Duplicate-send protection
    # ------------------------------------------------------------------

    def test_send_key_can_be_claimed_once(self):
        lead = self._lead()
        self.assertTrue(lead.ggd_claim_send_key("7-42"))
        self.assertEqual(lead.ggd_last_send_key, "7-42")
        self.assertTrue(lead.ggd_last_sent_at)

    def test_second_claim_of_same_key_is_refused(self):
        """This is the control that prevents a duplicate send."""
        lead = self._lead()
        lead.ggd_claim_send_key("7-42")
        self.assertFalse(lead.ggd_claim_send_key("7-42"))

    def test_a_new_draft_produces_a_claimable_key(self):
        """A genuinely new draft must still be sendable."""
        lead = self._lead()
        lead.ggd_claim_send_key("7-42")
        self.assertTrue(lead.ggd_claim_send_key("7-43"))
        self.assertEqual(lead.ggd_last_send_key, "7-43")

    def test_empty_send_key_is_refused(self):
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
