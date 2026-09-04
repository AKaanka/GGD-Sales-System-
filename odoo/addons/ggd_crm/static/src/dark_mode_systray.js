/** @odoo-module **/

/**
 * A dark-mode switch at the right of the top bar (#53).
 *
 * Odoo 19 community already compiles web.assets_web_dark, and the webclient
 * template already chooses it when color_scheme is "dark". The only missing
 * piece was the decision, which ir_http.py now takes from a cookie. This is
 * the control that sets it.
 *
 * The reload is required rather than merely convenient: the theme is a
 * different CSS bundle, chosen server-side while the page is rendered, not a
 * class toggled on the body. There is no way to swap it in place.
 */

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";

const COOKIE = "color_scheme";
const ONE_YEAR = 60 * 60 * 24 * 365;

export class GgdDarkModeToggle extends Component {
    static template = "ggd_crm.DarkModeToggle";
    static props = {};

    setup() {
        this.state = useState({ dark: this.currentScheme() === "dark" });
    }

    currentScheme() {
        const hit = document.cookie
            .split(";")
            .map((c) => c.trim())
            .find((c) => c.startsWith(`${COOKIE}=`));
        return hit ? hit.slice(COOKIE.length + 1) : "light";
    }

    get label() {
        return this.state.dark ? "Switch to light mode" : "Switch to dark mode";
    }

    onClick() {
        const next = this.state.dark ? "light" : "dark";
        // SameSite=Lax so it survives ordinary navigation. The value is a
        // display preference and carries nothing worth protecting.
        document.cookie = `${COOKIE}=${next};path=/;max-age=${ONE_YEAR};SameSite=Lax`;
        this.state.dark = !this.state.dark;
        window.location.reload();
    }
}

registry.category("systray").add(
    "ggd_crm.dark_mode",
    { Component: GgdDarkModeToggle },
    { sequence: 1 }
);
