/** @odoo-module **/

/**
 * The fit score, in the two shapes the Aurora design draws it.
 *
 *   default                 a 64px ring, a conic gradient filled to the value
 *                           with the number in the middle. The opportunity
 *                           form strip. options="{'size': 'sm'}" gives the
 *                           30px ring used in list rows.
 *   options="{'variant':    the number followed by a 46x5 bar. The kanban
 *   'bar'}"                 card, where a ring at card scale reads as an
 *                           avatar and the row has to stay one line high.
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
        variant: { type: String, optional: true },
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
        return this.props.variant === "bar"
            ? `width: ${this.value}%`
            : `--ggd-p: ${this.value}%`;
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
        {
            label: _t("Variant"),
            name: "variant",
            type: "selection",
            choices: [
                { label: _t("Ring"), value: "ring" },
                { label: _t("Bar"), value: "bar" },
            ],
        },
    ],
    extractProps: ({ options }) => ({ size: options.size, variant: options.variant }),
};

registry.category("fields").add("ggd_ring", ggdRingField);
