/** @odoo-module **/

/**
 * The selection bar above the pipeline (#58, extended by #67).
 *
 * It began as four chips - what can go out today, what the automation refused
 * to decide, which send has an unknown outcome, who has written back - and it
 * is now also where a salesperson narrows the board to the customers being
 * worked on: a country, a product group, a company type, and the handful of
 * named filters behind "More".
 *
 * Three rules hold the whole thing together:
 *
 * 1. **Nothing here is a filter of its own.** Every control toggles a search
 *    item that lives in the search view, so a click leaves a facet behind,
 *    the Filters menu shows it ticked, and "Save current search" keeps it.
 *    That is what makes a saved view a live Odoo favourite rather than a
 *    second, private idea of what a filter is.
 *
 * 2. **Odoo's own AND/OR is the AND/OR.** Each picker drives one search-view
 *    *field*, and `SearchModel._getFieldDomain` ORs the values of one field
 *    and ANDs different fields. So two countries mean "either", and a country
 *    and a product group mean "both", without a line of domain code here. A
 *    lead in two product groups matches once and is counted once, because a
 *    domain returns records rather than rows.
 *
 * 3. **The numbers describe what is on screen.** The counts come from
 *    `crm.lead.ggd_board_chip_counts(domain)` with the active search domain,
 *    so a chip counts inside the selection instead of across the database.
 *    The daily send cap is the exception and is printed apart from the chips
 *    and labelled system-wide, because it is a limit on the whole install and
 *    reads like a group quota when it sits beside a group count.
 *
 * The component renders nothing when the search view carries none of these
 * items, which is how it stays out of every other kanban and list in the
 * database.
 */

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

/** key: the key ggd_board_chip_counts() returns. filter: the search view filter name. */
const CHIPS = [
    { key: "sendable", filter: "ggd_chip_sendable", label: "Sendable today", check: true },
    { key: "needs_review", filter: "ggd_chip_needs_review", label: "Needs review" },
    { key: "unresolved_claim", filter: "ggd_chip_unresolved_claim", label: "Unresolved claim" },
    { key: "replies", filter: "ggd_chip_replies", label: "Replies" },
];

/**
 * field: the search-view field the picker drives.
 * options: the key ggd_board_selection_options() returns its values under.
 */
const PICKERS = [
    { key: "country", field: "country_id", label: "Country", options: "countries" },
    {
        key: "product_group",
        field: "ggd_product_group_ids",
        label: "Product group",
        options: "product_groups",
    },
    {
        key: "company_type",
        field: "ggd_company_type",
        label: "Company type",
        options: "company_types",
    },
];

/** The named filters behind "More", in the two groups the search view puts them in. */
const MORE = [
    {
        title: "Follow-up",
        filters: [
            { name: "ggd_follow_not_contacted", label: "Not contacted" },
            { name: "ggd_follow_awaiting_reply", label: "Awaiting a reply" },
            { name: "ggd_follow_up_due", label: "Follow-up due or late" },
        ],
    },
    {
        title: "Classification gaps",
        filters: [
            { name: "ggd_gap_country", label: "Country missing" },
            { name: "ggd_gap_product_group", label: "Product group missing" },
            { name: "ggd_gap_archived_group", label: "Only archived product groups" },
        ],
    },
];

export class GgdQuickFilters extends Component {
    static template = "ggd_crm.QuickFilters";
    static components = { Dropdown, CheckboxItem };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ counts: null, options: null });
        // Every count is answered against the search that is on screen, so a
        // stale reply must never win. The sequence is the whole guard: a
        // reply older than the last request asked is dropped.
        this.sequence = 0;
        onWillStart(async () => {
            this.state.options = await this.orm.call(
                "crm.lead",
                "ggd_board_selection_options",
                []
            );
            await this.loadCounts();
        });
        // Render first, then ask for the numbers. The ticks, the facets and
        // the Clear control all come out of the search query and are already
        // correct; waiting for the count round-trip before showing them made
        // a click on a picker look like it had missed.
        useBus(this.env.searchModel, "update", () => {
            this.render();
            this.loadCounts();
        });
    }

    async loadCounts() {
        const sequence = ++this.sequence;
        const counts = await this.orm.call("crm.lead", "ggd_board_chip_counts", [], {
            domain: this.env.searchModel.domain,
        });
        if (sequence === this.sequence) {
            this.state.counts = counts;
        }
    }

    // ------------------------------------------------------------------
    // Reading the query
    // ------------------------------------------------------------------

    /**
     * The values currently picked for one search-view field.
     *
     * `searchModel.query` is read directly because there is no accessor for
     * this: `getSearchItems()` reports whether a field item is active but not
     * which values made it active, and a picker has to tick the ones that are.
     */
    selectedValues(searchItemId) {
        return this.env.searchModel.query
            .filter((elem) => elem.searchItemId === searchItemId && elem.autocompleteValue)
            .map((elem) => elem.autocompleteValue);
    }

    /** True when an autocomplete value stands for this option's id. */
    holdsOption(autocompleteValue, optionId) {
        const value = autocompleteValue.value;
        return Array.isArray(value) ? value.includes(optionId) : value === optionId;
    }

    /**
     * The autocomplete value a picked option becomes.
     *
     * `in [id]` rather than `= id` for the two relational pickers: it reads
     * the same whether the field is a many2one or a many2many, and it is what
     * a value typed into the search bar for the same field would also become,
     * so the bar and the search bar agree on one facet.
     */
    autocompleteValue(picker, option) {
        if (picker.field === "ggd_company_type") {
            return { label: option.name, operator: "=", value: option.id };
        }
        return { label: option.name, operator: "in", value: [option.id] };
    }

    // ------------------------------------------------------------------
    // What the bar shows
    // ------------------------------------------------------------------

    get pickers() {
        const options = this.state.options;
        if (!options) {
            return [];
        }
        const out = [];
        for (const picker of PICKERS) {
            const [item] = this.env.searchModel.getSearchItems(
                (searchItem) =>
                    searchItem.type === "field" && searchItem.fieldName === picker.field
            );
            if (!item) {
                continue;
            }
            const selected = this.selectedValues(item.id);
            out.push({
                ...picker,
                id: item.id,
                groupId: item.groupId,
                active: selected.length > 0,
                values: (options[picker.options] || []).map((option) => ({
                    ...option,
                    active: selected.some((value) => this.holdsOption(value, option.id)),
                })),
            });
        }
        return out;
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
                groupId: item.groupId,
                active: Boolean(item.isActive),
                counter: String(counts[chip.key]),
                empty: !counts[chip.key],
            });
        }
        return out;
    }

    get moreGroups() {
        const groups = [];
        for (const group of MORE) {
            const filters = [];
            for (const filter of group.filters) {
                const [item] = this.env.searchModel.getSearchItems((i) => i.name === filter.name);
                if (item) {
                    filters.push({
                        ...filter,
                        id: item.id,
                        groupId: item.groupId,
                        active: Boolean(item.isActive),
                    });
                }
            }
            if (filters.length) {
                groups.push({ ...group, filters });
            }
        }
        return groups;
    }

    get moreActiveCount() {
        return this.moreGroups.reduce(
            (total, group) => total + group.filters.filter((f) => f.active).length,
            0
        );
    }

    /** True when this bar is what narrowed the view, so Clear has something to undo. */
    get hasSelection() {
        return (
            this.pickers.some((picker) => picker.active) ||
            this.chips.some((chip) => chip.active) ||
            this.moreActiveCount > 0
        );
    }

    get matching() {
        return this.state.counts ? this.state.counts.matching : null;
    }

    get cap() {
        return this.state.counts ? this.state.counts.cap : null;
    }

    get isEmpty() {
        return !this.pickers.length && !this.chips.length && !this.moreGroups.length;
    }

    // ------------------------------------------------------------------
    // Changing the query
    // ------------------------------------------------------------------

    toggleSearchItem(item) {
        this.env.searchModel.toggleSearchItem(item.id);
    }

    toggleValue(picker, option) {
        const selected = this.selectedValues(picker.id);
        const kept = selected.filter((value) => !this.holdsOption(value, option.id));
        if (kept.length === selected.length) {
            this.env.searchModel.addAutoCompletionValues(
                picker.id,
                this.autocompleteValue(picker, option)
            );
            return;
        }
        this.setValues(picker, kept);
    }

    /**
     * Replace the values of one field facet.
     *
     * Odoo can add a value to a field facet and can drop the facet whole; it
     * has nothing for removing one value of several. So the facet is dropped
     * and the survivors are put back, with notification blocked so the view
     * reloads once at the end rather than once per value.
     */
    setValues(picker, values) {
        const searchModel = this.env.searchModel;
        if (!values.length) {
            searchModel.deactivateGroup(picker.groupId);
            return;
        }
        searchModel.blockNotification = true;
        try {
            searchModel.deactivateGroup(picker.groupId);
            for (const value of values.slice(0, -1)) {
                searchModel.addAutoCompletionValues(picker.id, value);
            }
        } finally {
            searchModel.blockNotification = false;
        }
        searchModel.addAutoCompletionValues(picker.id, values.at(-1));
    }

    /**
     * Undo what this bar set, and only that.
     *
     * Not `clearFilters()`, which would also drop the pipeline's default
     * "My Pipeline" facet. That default is the salesperson's own scope and
     * putting it back is not obvious; a button inside this bar should clear
     * this bar.
     */
    clear() {
        const groupIds = new Set();
        for (const picker of this.pickers) {
            if (picker.active) {
                groupIds.add(picker.groupId);
            }
        }
        for (const chip of this.chips) {
            if (chip.active) {
                groupIds.add(chip.groupId);
            }
        }
        for (const group of this.moreGroups) {
            for (const filter of group.filters) {
                if (filter.active) {
                    groupIds.add(filter.groupId);
                }
            }
        }
        const ids = [...groupIds];
        if (!ids.length) {
            return;
        }
        const searchModel = this.env.searchModel;
        searchModel.blockNotification = true;
        try {
            for (const groupId of ids.slice(0, -1)) {
                searchModel.deactivateGroup(groupId);
            }
        } finally {
            searchModel.blockNotification = false;
        }
        searchModel.deactivateGroup(ids.at(-1));
    }
}

// The template extensions in ggd_quick_filters.xml render the bar inside
// web.KanbanView and web.ListView, so both controllers have to know the
// component by name. The list carries it too because the selection has to
// stay visible when a salesperson switches over to tick rows for a bulk
// action - that is the same selection, and losing sight of it there is how
// the wrong rows get changed.
KanbanController.components = { ...KanbanController.components, GgdQuickFilters };
ListController.components = { ...ListController.components, GgdQuickFilters };
