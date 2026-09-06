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
 * Both the app and the section are decided from the action on screen, not
 * from the menu the user clicked: a record opened from the review desk still
 * lights the review desk, and a page reached by its raw action URL names the
 * app that owns it rather than the one the session happens to remember. The
 * bar re-renders when the action manager finishes an update, which is the
 * same signal the breadcrumbs follow.
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

    /**
     * Odoo remembers the last app the user opened in the session, and a page
     * reached by its raw action URL - a bookmark, a link that carries an
     * action id - does not change it. Stock Odoo then shows the wrong app
     * name in the brand; this bar also lists that app's sections, so the
     * whole left half of it describes a screen the user is not on. The app
     * that owns the action on screen is the honest answer, and it is the one
     * ggdIsCurrent already looks in.
     */
    get currentApp() {
        const action = this.actionService.currentController?.action;
        if (!action) {
            return super.currentApp;
        }
        const remembered = super.currentApp;
        if (remembered && this.ggdMenuOwns(this.menuService.getMenuAsTree(remembered.id), action)) {
            return remembered;
        }
        const apps = this.menuService.getApps();
        for (const app of apps) {
            if (this.ggdMenuOwns(this.menuService.getMenuAsTree(app.id), action)) {
                return app;
            }
        }
        // No menu points at the screen. The CRM's pipeline is one: its menu
        // runs a server action, and the window action the server hands back
        // carries neither that menu's id nor a path. What it does carry is
        // the module it was declared in, and an app is declared in the module
        // it belongs to, so the two module names are the last honest link.
        const module = typeof action.xml_id === "string" ? action.xml_id.split(".")[0] : null;
        const owner =
            module && apps.find((app) => typeof app.xmlid === "string" && app.xmlid.split(".")[0] === module);
        return owner || remembered;
    },

    /** True when the menu, or one below it, is the action's own menu entry. */
    ggdMenuOwns(menu, action) {
        return this.ggdMatchesById(menu, String(action.id)) || this.ggdMatchesByPath(menu, action.path || null);
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

    /** A menu, or one below it, points at the action by id. A server action is skipped: it is not the screen. */
    ggdMatchesById(menu, id) {
        return Boolean(
            (menu.actionID && String(menu.actionID) === id && menu.actionModel !== "ir.actions.server") ||
                (menu.childrenTree || []).some((child) => this.ggdMatchesById(child, id))
        );
    },

    /** The same by the path the URL shows, which is what a menu behind a server action shares with the screen. */
    ggdMatchesByPath(menu, path) {
        return Boolean(
            (path && menu.actionPath && menu.actionPath === path) ||
                (menu.childrenTree || []).some((child) => this.ggdMatchesByPath(child, path))
        );
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
        const hit =
            sections.find((menu) => this.ggdMatchesById(menu, id)) ||
            sections.find((menu) => this.ggdMatchesByPath(menu, path));
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
