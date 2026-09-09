from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GgdProductGroup(models.Model):
    """What GGD sells, as a short managed list rather than as free text.

    The opportunity already carries `ggd_product_focus`, a paragraph a
    researcher wrote about what the company makes. That paragraph is worth
    reading and worthless to filter on: no two of them spell "wire" the same
    way. This model is the other half - a small, ordered, renameable list a
    salesperson picks from, so "Turkey + Wire + Manufacturer" is a search
    rather than a guess. Neither replaces the other, and the free text is
    never rewritten from a group.

    A lead may sit in several groups. That is a many2many and not a field per
    group on the lead, because a company that draws wire and rolls pipe is one
    company: one record, one chatter, one history, counted once.

    Groups are archived, not deleted. Odoo's `Many2many.read` sets
    `active_test=False`, so an archived group stays visible on every lead that
    carried it and no history is lost; `crm.lead.ggd_product_group_state` is
    what makes "this lead's only group is archived" findable afterwards.
    """

    _name = "ggd.product.group"
    _description = "GGD product group"
    _order = "sequence, name"

    name = fields.Char(
        string="Product group",
        required=True,
        help="Short name a salesperson picks from, for example Wire or Pipe.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order the group appears in on the pipeline selector.",
    )
    color = fields.Integer(string="Colour index")
    active = fields.Boolean(
        string="Active",
        default=True,
        help=(
            "Unticked, the group disappears from the pickers but stays on "
            "every opportunity that already carries it."
        ),
    )
    description = fields.Text(
        string="What belongs here",
        help="One or two lines telling the next person what to file here.",
    )
    lead_ids = fields.Many2many(
        "crm.lead",
        "ggd_lead_product_group_rel",
        "group_id",
        "lead_id",
        string="Opportunities in this group",
    )
    lead_count = fields.Integer(
        string="Opportunity count",
        compute="_compute_lead_count",
        help="Opportunities in this group that the current user may read.",
    )

    _unique_name = models.Constraint(
        "UNIQUE (name)",
        "A product group with this name already exists. Rename the existing"
        " one rather than adding a second spelling of it.",
    )

    def _compute_lead_count(self):
        """Counted through search_read_group, so record rules apply.

        Reading `lead_ids` would report opportunities the current user cannot
        open, which is a small leak with a large blast radius: the number on a
        configuration screen would say how many leads another salesperson
        holds.
        """
        counts = dict(
            self.env["crm.lead"]._read_group(
                [("ggd_product_group_ids", "in", self.ids)],
                groupby=["ggd_product_group_ids"],
                aggregates=["__count"],
            )
        )
        for group in self:
            group.lead_count = counts.get(group, 0)

    @api.constrains("name")
    def _check_name(self):
        for group in self:
            if not (group.name or "").strip():
                raise ValidationError(_("A product group needs a name."))

    def action_ggd_open_leads(self):
        """Open the pipeline filtered to this group, from the configuration list."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "crm.crm_lead_action_pipeline"
        )
        action.update(
            {
                "name": self.name,
                "domain": [
                    ("type", "=", "opportunity"),
                    ("ggd_product_group_ids", "in", self.ids),
                ],
                "context": {"default_type": "opportunity"},
            }
        )
        return action
