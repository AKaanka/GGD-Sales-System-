/** @odoo-module **/

/**
 * The quick-filter chips above the pipeline columns (#58).
 *
 * The design puts four chips between the control panel and the board:
 * what can go out today, what the automation refused to decide, which send
 * has an unknown outcome, and who has written back. They are the review
 * desk's four questions, asked from the board, and the point of them is that
 * the answer is visible without opening a menu - a count on a chip is seen,
 * a filter behind a dropdown is not.
 *
 * A chip does not filter by itself. It toggles the matching filter in the
 * search view, so clicking one leaves a facet behind, the Filters menu shows
 * it ticked, and a saved favourite keeps it. The domains live in the search
 * view and in ggd_board_chip_counts() on crm.lead; the two are documented as
 * one pair and have to be edited together.
 *
 * The component renders nothing when the search view has no ggd_chip_*
 * filters, which is how it stays out of every other kanban in the database.
 */

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

/** key: the key ggd_board_chip_counts() returns. filter: the search view filter name. */
const CHIPS = [
    { key: "sendable", filter: "ggd_chip_sendable", label: "Sendable today", check: true },
    { key: "needs_review", filter: "ggd_chip_needs_review", label: "Needs review" },
    { key: "unresolved_claim", filter: "ggd_chip_unresolved_claim", label: "Unresolved claim" },
    { key: "replies", filter: "ggd_chip_replies", label: "Replies" },
];

export class GgdQuickFilters extends Component {
    static template = "ggd_crm.QuickFilters";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ counts: null });
        onWillStart(() => this.loadCounts());
        // The counts are global, not scoped to the current filters, so a
        // toggle does not change them. Reloading anyway is one small read and
        // is what keeps them honest after an edit or a drag, which is the only
        // other thing that reaches this screen.
        useBus(this.env.searchModel, "update", () => this.loadCounts());
    }

    async loadCounts() {
        this.state.counts = await this.orm.call("crm.lead", "ggd_board_chip_counts", []);
    }

    /** The search items behind the chips, in the design's order, skipping any the view does not carry. */
    get chips() {
        const counts = this.state.counts;
        if (!counts) {
            return [];
        }
        const out = [];
        for (const chip of CHIPS) {
            const [item] = this.env.searchModel.getSearchItems((i) => i.name === chip.filter);
            if (!item) {
                continue;
            }
            out.push({
                ...chip,
                id: item.id,
                active: Boolean(item.isActive),
                counter:
                    chip.key === "sendable"
                        ? `${counts.sendable} / ${counts.cap}`
                        : String(counts[chip.key]),
                empty: !counts[chip.key],
            });
        }
        return out;
    }

    toggle(chip) {
        this.env.searchModel.toggleSearchItem(chip.id);
    }
}

// The template extension in ggd_quick_filters.xml renders the bar inside
// web.KanbanView, so the controller has to know the component by name.
KanbanController.components = { ...KanbanController.components, GgdQuickFilters };
