from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # Contact bases that are NOT, by themselves, a lawful basis for a first
    # marketing email under UWG s 7 Abs. 2 Nr. 2. See
    # docs/LAWFUL-CONTACT-PROCEDURE.md section 4. A record on one of these
    # bases can still be called or approached by other means; it cannot be
    # approved for automated email outreach.
    GGD_NO_EMAIL_BASES = (
        "trade_fair_no_optin",
        "referral",
        "other",
    )

    # Minimum length for the contact-basis note. The note must carry actual
    # evidence - a date, a source, a document reference - not a restatement of
    # the selection label. A length floor cannot enforce quality, but it does
    # stop "ok" and "yes" from passing as evidence.
    GGD_CONTACT_BASIS_NOTE_MIN_LENGTH = 20

    ggd_industry = fields.Char(string="Industry")
    ggd_product_focus = fields.Text(string="Product / capability focus")
    ggd_source_url = fields.Char(string="Research source URL")
    ggd_fit_score = fields.Integer(
        string="GGD fit score",
        help="LLM-assisted or manually reviewed fit score from 0 to 100.",
    )
    ggd_fit_summary = fields.Text(string="Fit assessment")
    ggd_personalization_angle = fields.Text(string="Personalisation angle")

    ggd_contact_basis = fields.Selection(
        selection=[
            ("consent", "Prior express consent — opt-in on file"),
            (
                "existing_customer",
                "Existing customer — all four UWG §7(3) conditions met",
            ),
            ("inbound", "Inbound enquiry — reply stays within its scope"),
            ("trade_fair", "Trade fair — opt-in recorded at the stand"),
            ("trade_fair_no_optin", "Trade fair — no opt-in (do not email)"),
            ("referral", "Referral / introduction (do not email)"),
            ("other", "Other — requires legal review (do not email)"),
        ],
        string="Contact basis",
        help=(
            "The label states the effect on email outreach. Bases marked "
            "'do not email' cannot be approved for automated outreach; use "
            "telephone, a warm introduction, or post instead. Operational "
            "record only — it does not replace legal review."
        ),
    )
    ggd_contact_basis_note = fields.Text(
        string="Contact-basis note",
        help=(
            "The evidence behind the contact basis: where and when it arose, "
            "and a reference that can be checked today. Required before "
            "outreach can be approved."
        ),
    )
    ggd_contact_basis_verified_at = fields.Datetime(
        string="Contact basis verified at",
        readonly=True,
        copy=False,
        help=(
            "Set only when a human approves outreach, so the age of the "
            "evidence is visible. Cleared when approval is revoked."
        ),
    )
    ggd_outreach_approved = fields.Boolean(
        string="Outreach approved",
        copy=False,
        tracking=True,
    )
    ggd_outreach_approved_by = fields.Many2one(
        "res.users",
        string="Approved by",
        readonly=True,
        copy=False,
    )
    ggd_outreach_approved_at = fields.Datetime(
        string="Approved at",
        readonly=True,
        copy=False,
    )
    ggd_do_not_contact = fields.Boolean(
        string="Do not contact",
        copy=False,
        tracking=True,
    )

    ggd_reply_category = fields.Selection(
        selection=[
            ("interested", "Interested"),
            ("meeting", "Meeting requested"),
            ("information", "Needs information"),
            ("objection", "Objection"),
            ("referral", "Referral to another person"),
            ("not_interested", "Not interested"),
            ("out_of_office", "Out of office"),
            ("unsubscribe", "Unsubscribe / stop"),
            ("unclear", "Unclear — manual review"),
        ],
        string="Latest reply category",
        copy=False,
        tracking=True,
    )
    ggd_reply_summary = fields.Text(string="Latest reply summary", copy=False)
    ggd_suggested_next_action = fields.Text(
        string="Suggested next action",
        copy=False,
    )
    ggd_ai_confidence = fields.Float(
        string="AI confidence",
        digits=(3, 2),
        copy=False,
        help="Confidence between 0.00 and 1.00. Low confidence requires manual review.",
    )
    ggd_ai_last_analyzed_at = fields.Datetime(
        string="Last AI analysis",
        readonly=True,
        copy=False,
    )
    ggd_last_message_id = fields.Char(
        string="Last email message ID",
        copy=False,
        index=True,
        help="Used by the automation layer to match replies to this opportunity.",
    )
    ggd_last_send_key = fields.Char(
        string="Last send key",
        copy=False,
        index=True,
        help=(
            "Idempotency key for outbound sending, formed from the opportunity "
            "ID and the identifier of the draft being sent. The send workflow "
            "must claim this key BEFORE calling SMTP, so that a crash between "
            "sending and recording cannot result in a second send. A repeat run "
            "that finds the key already claimed must stop before SMTP."
        ),
    )
    ggd_last_sent_at = fields.Datetime(
        string="Last outbound send at",
        readonly=True,
        copy=False,
    )
    ggd_last_message_date = fields.Date(
        string="Last message date",
        copy=False,
        readonly=True,
        help="Latest date of any message (sent or received); used for follow-up scheduling.",
    )

    @api.constrains("ggd_fit_score")
    def _check_ggd_fit_score(self):
        for lead in self:
            if not 0 <= lead.ggd_fit_score <= 100:
                raise ValidationError(_("GGD fit score must be between 0 and 100."))

    @api.constrains("ggd_ai_confidence")
    def _check_ggd_ai_confidence(self):
        for lead in self:
            if not 0 <= lead.ggd_ai_confidence <= 1:
                raise ValidationError(_("AI confidence must be between 0.00 and 1.00."))

    def _ggd_check_approval_allowed(self, do_not_contact, contact_basis, basis_note):
        """Raise if this combination may not be approved for email outreach.

        Shared by the approval button, write() and create(), so that setting
        ggd_outreach_approved directly is subject to the same rules. A gate
        enforced only in a UI button is not a gate. Takes plain values rather
        than reading self, so it can also run before a record exists.
        """
        if do_not_contact:
            raise ValidationError(
                _("This opportunity is marked Do not contact and cannot be approved.")
            )
        if not contact_basis:
            raise ValidationError(
                _("Record and review the contact basis before approving outreach.")
            )
        if contact_basis in self.GGD_NO_EMAIL_BASES:
            label = dict(
                self._fields["ggd_contact_basis"].selection
            ).get(contact_basis, contact_basis)
            raise ValidationError(
                _(
                    "Contact basis '%(label)s' is not a lawful basis for a first "
                    "marketing email under UWG §7. Outreach cannot be approved. "
                    "Use a telephone call, a warm introduction, or post instead — "
                    "or record the opt-in evidence and change the basis.",
                    label=label,
                )
            )
        note = (basis_note or "").strip()
        if len(note) < self.GGD_CONTACT_BASIS_NOTE_MIN_LENGTH:
            raise ValidationError(
                _(
                    "Record the evidence for the contact basis before approving. "
                    "State where and when it arose and give a reference that can "
                    "be checked today — not a restatement of the label."
                )
            )

    def action_ggd_approve_outreach(self):
        for lead in self:
            lead._ggd_check_approval_allowed(
                lead.ggd_do_not_contact,
                lead.ggd_contact_basis,
                lead.ggd_contact_basis_note,
            )
            lead.write(
                {
                    "ggd_outreach_approved": True,
                    "ggd_outreach_approved_by": self.env.user.id,
                    "ggd_outreach_approved_at": fields.Datetime.now(),
                    "ggd_contact_basis_verified_at": fields.Datetime.now(),
                }
            )
            lead.message_post(body=_("GGD outreach approved for manual-gated automation."))
        return True

    def ggd_claim_send_key(self, send_key):
        """Atomically claim a send key. Returns True if this caller may send.

        Called by the outbound workflow immediately BEFORE SMTP. The write
        happens first so that a crash between claiming and sending leaves the
        key claimed — the failure mode is a missed send that a human can
        investigate, never a duplicate send.

        Returns False if the key is already claimed, which means the send has
        already happened or is in flight. The caller must then stop without
        contacting anyone.
        """
        self.ensure_one()
        if not send_key:
            raise ValidationError(_("A send key is required before sending."))
        if self.ggd_last_send_key == send_key:
            return False
        self.write({
            "ggd_last_send_key": send_key,
            "ggd_last_sent_at": fields.Datetime.now(),
        })
        return True

    def ggd_finalize_send(self):
        """Mark send as complete and revoke approval to prevent resends.

        Called by the outbound workflow immediately AFTER successful SMTP.
        Updates message date for follow-up scheduling and clears approval.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({
            "ggd_last_message_date": now.date(),
            "ggd_outreach_approved": False,
            "ggd_outreach_approved_by": False,
            "ggd_outreach_approved_at": False,
        })
        self.message_post(
            body=_("GGD outreach sent. Approval revoked; reply analysis will run on inbound.")
        )

    def action_ggd_revoke_outreach(self):
        for lead in self:
            lead.write(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                }
            )
            lead.message_post(body=_("GGD outreach approval revoked."))
        return True

    @api.onchange("ggd_do_not_contact")
    def _onchange_ggd_do_not_contact(self):
        if self.ggd_do_not_contact:
            self.ggd_outreach_approved = False

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("ggd_do_not_contact"):
                values.update(
                    {
                        "ggd_outreach_approved": False,
                        "ggd_outreach_approved_by": False,
                        "ggd_outreach_approved_at": False,
                        "ggd_contact_basis_verified_at": False,
                    }
                )
            elif values.get("ggd_outreach_approved"):
                # Closes the same hole as write(): a record must not be able to
                # come into existence already approved on a basis that could
                # never have been approved afterwards.
                self._ggd_check_approval_allowed(
                    values.get("ggd_do_not_contact"),
                    values.get("ggd_contact_basis"),
                    values.get("ggd_contact_basis_note"),
                )
        return super().create(vals_list)

    def write(self, values):
        if values.get("ggd_do_not_contact"):
            values.update(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                }
            )
        elif values.get("ggd_outreach_approved") is False:
            values.update(
                {
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                    "ggd_contact_basis_verified_at": False,
                }
            )
        elif values.get("ggd_outreach_approved"):
            # Approval is being granted directly rather than through the
            # button. Apply the same checks, evaluated against the values this
            # write will leave behind.
            for lead in self:
                lead._ggd_check_approval_allowed(
                    values.get("ggd_do_not_contact", lead.ggd_do_not_contact),
                    values.get("ggd_contact_basis", lead.ggd_contact_basis),
                    values.get("ggd_contact_basis_note", lead.ggd_contact_basis_note),
                )
        return super().write(values)
