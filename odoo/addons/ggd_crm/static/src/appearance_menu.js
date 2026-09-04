/** @odoo-module **/

/**
 * The appearance menu at the right of the top bar: light or dark, and one of
 * three tones. It replaces the dark-mode toggle from #53.
 *
 * Both choices live on <html> as data attributes that ggd_theme.scss keys
 * its custom properties on, so a change repaints in place. The scheme is
 * also written to the color_scheme cookie that ir_http.py reads: Odoo's own
 * few dark stylesheets (calendar, emoji picker, file viewer) are picked
 * server-side from that cookie, so they follow on the next page load. The
 * tone is a browser preference and lives in localStorage; like the cookie it
 * is per-browser rather than per-user, which for a single-operator CRM is
 * the right trade and needs no field on res.users.
 *
 * applyAppearance() runs once at module load, before the web client mounts,
 * so the first paint already carries the choice.
 */

import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { Component, useState } from "@odoo/owl";

const COOKIE = "color_scheme";
const ONE_YEAR = 60 * 60 * 24 * 365;
const TONE_KEY = "ggd_tone";

export const TONES = [
    { id: "aurora", label: "Aurora", swatch: "linear-gradient(135deg, #4fd6c8, #a08cff)" },
    { id: "ember", label: "Ember", swatch: "linear-gradient(135deg, #f0a35c, #f27b8e)" },
    { id: "graphite", label: "Graphite", swatch: "linear-gradient(135deg, #c6f542, #9aa0aa)" },
];

function readCookie(name) {
    const hit = document.cookie
        .split(";")
        .map((c) => c.trim())
        .find((c) => c.startsWith(`${name}=`));
    return hit ? hit.slice(name.length + 1) : "";
}

export function currentScheme() {
    return readCookie(COOKIE) === "dark" ? "dark" : "light";
}

export function currentTone() {
    try {
        const tone = localStorage.getItem(TONE_KEY);
        return TONES.some((t) => t.id === tone) ? tone : "aurora";
    } catch {
        return "aurora";
    }
}

export function applyAppearance(scheme, tone) {
    const root = document.documentElement;
    root.dataset.ggdScheme = scheme;
    root.dataset.ggdTone = tone;
}

applyAppearance(currentScheme(), currentTone());

export class GgdAppearanceMenu extends Component {
    static template = "ggd_crm.AppearanceMenu";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.tones = TONES;
        this.state = useState({ scheme: currentScheme(), tone: currentTone() });
    }

    get isDark() {
        return this.state.scheme === "dark";
    }

    setScheme(scheme) {
        // SameSite=Lax so it survives ordinary navigation. The value is a
        // display preference and carries nothing worth protecting.
        document.cookie = `${COOKIE}=${scheme};path=/;max-age=${ONE_YEAR};SameSite=Lax`;
        this.state.scheme = scheme;
        applyAppearance(scheme, this.state.tone);
    }

    setTone(tone) {
        try {
            localStorage.setItem(TONE_KEY, tone);
        } catch {
            // private mode or blocked storage: the choice still applies to this page
        }
        this.state.tone = tone;
        applyAppearance(this.state.scheme, tone);
    }
}

registry.category("systray").add(
    "ggd_crm.appearance",
    { Component: GgdAppearanceMenu },
    { sequence: 1 }
);
