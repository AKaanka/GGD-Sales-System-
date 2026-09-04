/** @odoo-module **/

/**
 * A ring for the fit score: a conic gradient that fills to the value, with
 * the number in the middle. Used at 64px on the opportunity form strip and
 * at 30px (options="{'size': 'sm'}") on kanban cards and list rows.
 *
 * Read-only by design: the score is written by GGD-01, never by hand.
 */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class GgdRingField extends Component {
    static template = "ggd_crm.RingField";
    static props = {
        ...standardFieldProps,
        size: { type: String, optional: true },
    };

    get raw() {
        return this.props.record.data[this.props.name];
    }

    get hasValue() {
        return Number.isFinite(this.raw) && this.raw > 0;
    }

    get value() {
        return this.hasValue ? Math.max(0, Math.min(100, Math.round(this.raw))) : 0;
    }

    get style() {
        return `--ggd-p: ${this.value}%`;
    }

    get title() {
        return this.hasValue ? `${_t("Fit score")}: ${this.value} / 100` : _t("No fit score yet");
    }
}

export const ggdRingField = {
    component: GgdRingField,
    displayName: _t("Score ring"),
    supportedTypes: ["integer", "float"],
    supportedOptions: [
        {
            label: _t("Size"),
            name: "size",
            type: "selection",
            choices: [
                { label: _t("Large"), value: "lg" },
                { label: _t("Small"), value: "sm" },
            ],
        },
    ],
    extractProps: ({ options }) => ({ size: options.size }),
};

registry.category("fields").add("ggd_ring", ggdRingField);
