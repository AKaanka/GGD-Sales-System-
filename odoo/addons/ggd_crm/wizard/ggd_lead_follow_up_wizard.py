from datetime import timedelta
from uuid import uuid4

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GgdLeadFollowUpWizard(models.TransientModel):
    """One follow-up activity on each ticked opportunity, once.

    Pressing Apply twice, or a browser retrying the request, must not book the
    same call twice. The guard is the one already in the addon: every wizard
    carries a `batch_key` minted when it opens, and each activity is recorded
    in `ggd.opportunity.action.log` under (opportunity, schedule_activity,
    that key). The unique constraint on those three is what makes the second
    attempt a no-op instead of a second reminder, and it holds whether the
    repeat comes from the button, from a refresh, or from JSON-2.

    This never sends email. Assigning an activity to somebody normally
    notifies them, so the create runs under `mail_activity_quick_update`, the
    same context the connector's own scheduling uses: the activity still
    appears in the assignee's Odoo inbox and on the record, and nothing is
    queued for delivery.
    """

    _name = "ggd.lead.followup.wizard"
    _inherit = ["ggd.lead.bulk.action"]
    _description = "Schedule a follow-up on the selected opportunities"

    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Activity type",
        required=True,
        default=lambda self: self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        ),
        domain="[('res_model', 'in', [False, 'crm.lead'])]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False), ('active', '=', True)]",
        help="The one person every activity in this batch is assigned to.",
    )
    date_deadline = fields.Date(
        string="Due on",
        required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=7),
    )
    summary = fields.Char(
        string="Summary",
        required=True,
        help="The one line the assignee sees in their activity list.",
    )
    note = fields.Text(string="Note")
    batch_key = fields.Char(
        string="Batch key",
        required=True,
        readonly=True,
        default=lambda self: uuid4().hex,
        help=(
            "Minted when this wizard opened. It is what makes a repeated "
            "Apply return the first result instead of a second activity."
        ),
    )

    @api.depends("lead_ids", "state", "activity_type_id", "user_id", "date_deadline")
    def _compute_ggd_plan(self):
        return super()._compute_ggd_plan()

    @api.constrains("date_deadline")
    def _check_date_deadline(self):
        """The connector's own bounds, for the same two reasons.

        A deadline in the past is a follow-up nobody was ever going to be
        reminded about in time, and one more than a year out is far more
        likely a mistyped year than a plan.
        """
        Lead = self.env["crm.lead"]
        today = fields.Date.context_today(self)
        for wizard in self:
            if not wizard.date_deadline:
                continue
            if wizard.date_deadline < today:
                raise ValidationError(
                    _("The due date is in the past. Follow-ups are scheduled forward.")
                )
            horizon = today + timedelta(days=Lead.GGD_ACTION_MAX_DEADLINE_DAYS)
            if wizard.date_deadline > horizon:
                raise ValidationError(
                    _(
                        "The due date is more than %(days)s days away, which is "
                        "more likely a mistyped year than a plan.",
                        days=Lead.GGD_ACTION_MAX_DEADLINE_DAYS,
                    )
                )

    def _ggd_blockers(self, leads):
        reasons = super()._ggd_blockers(leads)
        already = self.env["ggd.opportunity.action.log"].search(
            [
                ("lead_id", "in", leads.ids),
                ("action", "=", "schedule_activity"),
                ("idempotency_key", "=", self.batch_key),
            ]
        )
        for row in already:
            reasons.setdefault(
                row.lead_id.id,
                _("This request already scheduled a follow-up on it."),
            )
        return reasons

    def _ggd_unchanged_label(self):
        return _("this request had already scheduled them")

    def _ggd_apply(self, leads):
        activity_type = self.activity_type_id
        assignee = self.user_id
        deadline = self.date_deadline
        model_id = self.env["ir.model"]._get_id("crm.lead")
        note = (self.note or "").strip()
        body = Markup("<p>%s</p>") % escape(note) if note else False
        changed = 0
        for lead in leads:
            # Posted before the activity is created, not after. Creating one
            # subscribes its assignee to the record, and a note posted
            # afterwards would notify somebody this same call had just signed
            # up. The transaction covers both, so a refused create takes the
            # note with it.
            lead.message_post(
                body=_(
                    "GGD follow-up scheduled: %(type)s due %(deadline)s for "
                    "%(user)s.",
                    type=activity_type.name,
                    deadline=fields.Date.to_string(deadline),
                    user=assignee.name,
                )
            )
            activity = (
                self.env["mail.activity"]
                .with_context(mail_activity_quick_update=True)
                .create(
                    {
                        "res_model_id": model_id,
                        "res_id": lead.id,
                        "activity_type_id": activity_type.id,
                        "summary": self.summary,
                        "note": body,
                        "date_deadline": deadline,
                        "user_id": assignee.id,
                    }
                )
            )
            lead._ggd_action_record(
                "schedule_activity",
                self.batch_key,
                summary=self.summary,
                result_ref=str(activity.id),
            )
            changed += 1
        return changed, 0
