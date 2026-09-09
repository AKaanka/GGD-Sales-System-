from odoo import _, api, fields, models


class GgdLeadStageWizard(models.TransientModel):
    """Move the ticked opportunities to one stage, under the existing rules.

    The rules are not restated here. `crm.lead._ggd_stage_change_blocker`
    is the same method the ChatGPT connector's `transition_stage` action asks
    (issue #65), so a stage a person may not reach in bulk is a stage the
    assistant may not reach either, and widening one widens both. What it
    refuses: a stage outside the documented working set, a won stage, and
    Contacted for a record with no confirmed send and no recorded manual
    contact.

    A stage change writes `stage_id` and nothing else. It does not approve
    outreach, claim a send key, stamp a send, or start an n8n workflow; the
    ordinary `crm.lead.write` guards still stand behind it.
    """

    _name = "ggd.lead.stage.wizard"
    _inherit = ["ggd.lead.bulk.action"]
    _description = "Move the selected opportunities to a stage"

    allowed_stage_ids = fields.Many2many(
        "crm.stage",
        string="Stages this action may set",
        compute="_compute_allowed_stage_ids",
    )
    stage_id = fields.Many2one(
        "crm.stage",
        string="Move to stage",
        required=True,
        domain="[('id', 'in', allowed_stage_ids)]",
    )

    @api.depends("lead_ids")
    def _compute_allowed_stage_ids(self):
        """The documented working stages, looked up by name, won ones dropped.

        The dropdown is built from the same constant the blocker checks, so a
        stage that would be refused is never offered in the first place. The
        blocker still runs on apply: the list is a courtesy, not the control.
        """
        Stage = self.env["crm.stage"]
        names = self.env["crm.lead"].GGD_ACTION_STAGES
        stages = Stage.search([("name", "in", list(names))])
        allowed = stages.filtered(lambda stage: not stage.is_won)
        for wizard in self:
            wizard.allowed_stage_ids = allowed

    @api.depends("lead_ids", "state", "stage_id")
    def _compute_ggd_plan(self):
        return super()._compute_ggd_plan()

    def _ggd_blockers(self, leads):
        reasons = super()._ggd_blockers(leads)
        stage = self.stage_id
        if not stage:
            return reasons
        for lead in leads:
            if lead.id in reasons:
                continue
            blocker = lead._ggd_stage_change_blocker(stage)
            if blocker is not None:
                reasons[lead.id] = blocker[1]
        return reasons

    def _ggd_unchanged_label(self):
        return _("they are in that stage already")

    def _ggd_apply(self, leads):
        stage = self.stage_id
        changed = unchanged = 0
        for lead in leads:
            if lead.stage_id == stage:
                unchanged += 1
                continue
            previous = lead.stage_id.name or _("no stage")
            lead.write({"stage_id": stage.id})
            lead.message_post(
                body=_(
                    "GGD stage moved from %(previous)s to %(stage)s.",
                    previous=previous,
                    stage=stage.name,
                )
            )
            changed += 1
        return changed, unchanged
