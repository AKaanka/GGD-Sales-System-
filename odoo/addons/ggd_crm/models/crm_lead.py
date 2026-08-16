from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

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
            ("consent", "Prior consent"),
            ("existing_customer", "Existing customer relationship"),
            ("inbound", "Inbound request"),
            ("trade_fair", "Trade fair / in-person contact"),
            ("referral", "Referral / introduction"),
            ("other", "Other — requires review"),
        ],
        string="Contact basis",
        help="Operational record only. It does not replace legal review.",
    )
    ggd_contact_basis_note = fields.Text(string="Contact-basis note")
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

    def action_ggd_approve_outreach(self):
        for lead in self:
            if lead.ggd_do_not_contact:
                raise ValidationError(
                    _("This opportunity is marked Do not contact and cannot be approved.")
                )
            if not lead.ggd_contact_basis:
                raise ValidationError(
                    _("Record and review the contact basis before approving outreach.")
                )
            lead.write(
                {
                    "ggd_outreach_approved": True,
                    "ggd_outreach_approved_by": self.env.user.id,
                    "ggd_outreach_approved_at": fields.Datetime.now(),
                }
            )
            lead.message_post(body=_("GGD outreach approved for manual-gated automation."))
        return True

    def action_ggd_revoke_outreach(self):
        for lead in self:
            lead.write(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                }
            )
            lead.message_post(body=_("GGD outreach approval revoked."))
        return True

    @api.onchange("ggd_do_not_contact")
    def _onchange_ggd_do_not_contact(self):
        if self.ggd_do_not_contact:
            self.ggd_outreach_approved = False

    def write(self, values):
        if values.get("ggd_do_not_contact"):
            values.update(
                {
                    "ggd_outreach_approved": False,
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                }
            )
        elif values.get("ggd_outreach_approved") is False:
            values.update(
                {
                    "ggd_outreach_approved_by": False,
                    "ggd_outreach_approved_at": False,
                }
            )
        return super().write(values)
