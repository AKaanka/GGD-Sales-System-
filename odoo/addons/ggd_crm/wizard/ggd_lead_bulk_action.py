from odoo import _, api, fields, models
from odoo.exceptions import UserError


class GgdLeadBulkAction(models.AbstractModel):
    """What the three bulk opportunity actions of issue #67 have in common.

    All three answer the same four questions, and answering them in one place
    is what stops the three from drifting apart:

    * **What is selected.** Only `active_ids`, the records the user ticked.
      Odoo's list view resolves "select all" into real ids before the action
      runs, so a select-all is a real, countable list rather than a domain
      that keeps growing. `active_domain` is in the context too and is
      deliberately ignored: it is the current search, not the selection, and
      reading it would turn three ticked rows into the whole pipeline.

    * **What will happen.** The wizard shows the selection count, how many
      records the change applies to, and how many are blocked and why, before
      anything is written. The preview is not the enforcement: `_ggd_apply`
      partitions again at apply time, so a record that changed in between is
      caught.

    * **Who may.** Odoo's own write access decides, per record, through
      `_filtered_access("write")`. A user who may edit six of the ten
      selected opportunities changes six and is told about the other four.

    * **What happened.** Applied, unchanged and blocked are counted and
      shown with their reasons. Partial success is allowed and is never
      silent; the alternative - refusing the whole batch because one record
      is suppressed - would leave a salesperson picking rows by hand until
      the batch happens to be clean.

    Nothing here sends email, approves outreach, or starts an outbound
    workflow, and no subclass may: every write goes through the ordinary
    `crm.lead` guards, which is where the outbound gate lives.
    """

    _name = "ggd.lead.bulk.action"
    _description = "Shared machinery for the GGD bulk opportunity actions"

    lead_ids = fields.Many2many(
        "crm.lead",
        string="Selected opportunities",
        readonly=True,
        # An archived opportunity has to stay in the selection. Odoo drops
        # inactive records when it turns an x2many into a recordset, and a
        # record that disappears between the tick and the wizard is the worst
        # of the possible answers: it is neither changed nor reported.
        context={"active_test": False},
        help="Exactly the opportunities that were ticked in the list.",
    )
    state = fields.Selection(
        [("plan", "About to apply"), ("done", "Applied")],
        default="plan",
        readonly=True,
    )
    selected_count = fields.Integer(
        string="Selected", compute="_compute_ggd_plan"
    )
    ready_count = fields.Integer(
        string="Will change", compute="_compute_ggd_plan"
    )
    blocked_count = fields.Integer(
        string="Blocked", compute="_compute_ggd_plan"
    )
    blocked_summary = fields.Text(
        string="Why they are blocked", compute="_compute_ggd_plan"
    )
    result_summary = fields.Text(string="Result", readonly=True)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "lead_ids" not in fields_list:
            return values
        context = self.env.context
        active_model = context.get("active_model")
        if active_model and active_model != "crm.lead":
            raise UserError(
                _("This action runs on opportunities, not on %s.", active_model)
            )
        active_ids = context.get("active_ids")
        if not active_ids and context.get("active_id"):
            active_ids = [context["active_id"]]
        if not active_ids:
            raise UserError(
                _("Tick the opportunities to change before opening this action.")
            )
        values["lead_ids"] = [(6, 0, list(active_ids))]
        return values

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _ggd_blockers(self, leads):
        """Reasons this particular action cannot touch a record.

        Returns {lead id: reason}. Subclasses add their own rules; this one
        holds the two that apply whatever the action is. Access is not here:
        it is checked in `_ggd_partition`, before any state is read, so a
        record the user may not write is never described back to them.
        """
        reasons = {}
        for lead in leads:
            if not lead.active:
                reasons[lead.id] = _("Archived. Restore it in Odoo first.")
        return reasons

    def _ggd_partition(self):
        """(records this action will change, {lead id: reason it will not})."""
        self.ensure_one()
        leads = self.lead_ids
        writable = leads._filtered_access("write")
        reasons = {
            lead.id: _("You do not have permission to change this opportunity.")
            for lead in leads - writable
        }
        reasons.update(self._ggd_blockers(writable))
        ready = leads.filtered(lambda lead: lead.id not in reasons)
        return ready, reasons

    @staticmethod
    def _ggd_group_reasons(reasons):
        """One line per distinct reason, with how many records it stopped."""
        tally = {}
        for reason in reasons.values():
            tally[reason] = tally.get(reason, 0) + 1
        return "\n".join(
            "%s - %s" % (count, reason)
            for reason, count in sorted(tally.items(), key=lambda item: -item[1])
        )

    # Every subclass repeats this list with its own fields added. Odoo reads
    # the dependencies off the method that wins the MRO, so an override that
    # named only its own field would silently stop reacting to a new
    # selection.
    @api.depends("lead_ids", "state")
    def _compute_ggd_plan(self):
        for wizard in self:
            if wizard.state == "done":
                # The plan described a selection that has already been
                # applied; recomputing it would print a second, contradictory
                # set of numbers beside the result.
                wizard.selected_count = len(wizard.lead_ids)
                wizard.ready_count = 0
                wizard.blocked_count = 0
                wizard.blocked_summary = False
                continue
            ready, reasons = wizard._ggd_partition()
            wizard.selected_count = len(wizard.lead_ids)
            wizard.ready_count = len(ready)
            wizard.blocked_count = len(reasons)
            wizard.blocked_summary = wizard._ggd_group_reasons(reasons) or False

    # ------------------------------------------------------------------
    # Applying
    # ------------------------------------------------------------------

    def _ggd_apply(self, leads):
        """Do the work on `leads`. Returns (changed count, unchanged count)."""
        raise NotImplementedError

    def _ggd_unchanged_label(self):
        return _("already as requested")

    def action_ggd_apply(self):
        """Apply once. A second call returns the first result, unchanged.

        Not an error, on purpose: the second call is nearly always the same
        request arriving twice - a double click, a browser retry, a repeated
        JSON-2 call - and answering it with the receipt it already earned is
        what makes the operation safe to retry. Applying different settings
        to the same selection means closing this and starting again, which is
        also what the form offers once it is done.
        """
        self.ensure_one()
        if self.state == "done":
            return self._ggd_result_action()
        ready, reasons = self._ggd_partition()
        changed, unchanged = self._ggd_apply(ready)
        # Written as "label: number" rather than "N opportunities were ..."
        # so the sentence stays correct at one as well as at forty, in every
        # language, without a plural form per line.
        lines = [
            _("Selected: %(count)s", count=len(self.lead_ids)),
            _("Changed: %(count)s", count=changed),
        ]
        if unchanged:
            lines.append(
                _(
                    "Left alone (%(why)s): %(count)s",
                    count=unchanged,
                    why=self._ggd_unchanged_label(),
                )
            )
        if reasons:
            lines.append(_("Blocked: %(count)s", count=len(reasons)))
            lines.append(self._ggd_group_reasons(reasons))
        self.write({"state": "done", "result_summary": "\n".join(lines)})
        return self._ggd_result_action()

    def _ggd_result_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": _("Result"),
        }
