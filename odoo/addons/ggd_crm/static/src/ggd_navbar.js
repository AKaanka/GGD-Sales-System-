/** @odoo-module **/

/**
 * The top bar from the Aurora design (#58).
 *
 * Odoo's NavBar shows the current app's name as the brand and lists the
 * app's sections without saying which one the user is in. The design puts
 * the product name where the app name was and lights the current section.
 * The templates in ggd_navbar.xml do the markup; this file gives NavBar
 * the two answers the templates ask for, and adds the search button.
 *
 * "Current section" is decided from the action on screen, not from the
 * menu the user clicked: a record opened from the review desk still lights
 * the review desk. The bar re-renders when the action manager finishes an
 * update, which is the same signal the breadcrumbs follow.
 */

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

patch(NavBar.prototype, {
    setup() {
        super.setup();
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this.render());
    },

    /** The app name stays visible outside the CRM, where the sections alone would not say where the user is. */
    get ggdShowAppName() {
        const app = this.currentApp;
        return Boolean(app && app.xmlid !== "crm.crm_menu_root");
    },

    /**
     * A menu points at an action by id (actionID) and, since Odoo 18, by the
     * path the URL shows (actionPath). The id is enough for a window action;
     * a menu behind a server action - the CRM's own "My Pipeline" is one -
     * carries the server action's id while the screen shows the window
     * action it ran, so the path is what those two share.
     */
    ggdIsCurrent(section) {
        return Boolean(section) && this.ggdCurrentSectionId === section.id;
    },

    /** One section at most: an id match anywhere wins over a path match, and the first section in menu order wins a tie. */
    get ggdCurrentSectionId() {
        const controller = this.actionService.currentController;
        const action = controller && controller.action;
        if (!action) {
            return null;
        }
        const id = String(action.id);
        const path = action.path || null;
        const sections = this.currentAppSections;
        const byId = (menu) =>
            (menu.actionID && String(menu.actionID) === id && menu.actionModel !== "ir.actions.server") ||
            (menu.childrenTree || []).some(byId);
        const byPath = (menu) =>
            (path && menu.actionPath && menu.actionPath === path) || (menu.childrenTree || []).some(byPath);
        const hit = sections.find(byId) || sections.find(byPath);
        return hit ? hit.id : null;
    },
});

export class GgdSearchButton extends Component {
    static template = "ggd_crm.SearchButton";
    static props = {};

    setup() {
        this.command = useService("command");
    }

    open() {
        this.command.openMainPalette({});
    }
}

registry.category("systray").add("ggd_crm.search", { Component: GgdSearchButton }, { sequence: 100 });
