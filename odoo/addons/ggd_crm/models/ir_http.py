from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def color_scheme(self):
        """Serve Odoo's dark stylesheets when the browser asks for them.

        Community ships web.assets_web_dark and the template that chooses it,
        but color_scheme() returns "light" unconditionally - the hook where
        Enterprise reads a user preference. The theme is therefore compiled
        and never served. This fills in the decision.

        The signal is a cookie because Odoo already reads one by that name in
        its own offline page, so this follows an existing convention rather
        than inventing a second one. It also means no field on res.users, no
        migration, and no state to carry through an addon upgrade. The cost is
        that the choice is per-browser rather than per-user, which for a
        single-operator CRM is the right trade.

        Anything other than "dark" falls through to super(), so a stray or
        corrupted cookie cannot leave the interface unrenderable.
        """
        if request and request.httprequest.cookies.get("color_scheme") == "dark":
            return "dark"
        return super().color_scheme()
