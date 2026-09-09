from odoo import _, api, fields, models


class GgdLeadGroupWizard(models.TransientModel):
    """Add product groups to the ticked opportunities, keeping what is there.

    Add is the only mode, and that is the design rather than a first version.
    A bulk classification that could replace would sooner or later be run by
    somebody who meant to add, and the groups it silently dropped would be
    unrecoverable - the m2m keeps no history of its own. Removing a group is
    a one-record edit on the opportunity, where it is visible.

    A suppressed opportunity may still be classified. Do not contact stops
    outreach; it does not mean the company stopped making wire, and refusing
    to file those records would leave a permanent unclassifiable corner of
    the pipeline.
    """

    _name = "ggd.lead.group.wizard"
    _inherit = ["ggd.lead.bulk.action"]
    _description = "Add product groups to the selected opportunities"

    group_ids = fields.Many2many(
        "ggd.product.group",
        string="Product groups to add",
        required=True,
        domain=[("active", "=", True)],
        help="Added to whatever each opportunity already carries.",
    )

    @api.depends("lead_ids", "state", "group_ids")
    def _compute_ggd_plan(self):
        return super()._compute_ggd_plan()

    def _ggd_unchanged_label(self):
        return _("they already carry every one of these groups")

    def _ggd_apply(self, leads):
        groups = self.group_ids
        changed = unchanged = 0
        for lead in leads:
            missing = groups - lead.ggd_product_group_ids
            if not missing:
                unchanged += 1
                continue
            # (4, id) links; it never replaces. Writing (6, 0, ids) here is
            # the one mistake this wizard exists to make impossible.
            lead.write(
                {"ggd_product_group_ids": [(4, group.id) for group in missing]}
            )
            lead.message_post(
                body=_(
                    "GGD product groups added: %(groups)s.",
                    groups=", ".join(missing.mapped("name")),
                )
            )
            changed += 1
        return changed, unchanged
