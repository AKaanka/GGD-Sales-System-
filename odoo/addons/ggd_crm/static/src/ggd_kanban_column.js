/** @odoo-module **/

/**
 * The two things a pipeline column has to do that Odoo's does not (#58).
 *
 * 1. Scroll inside a box of its own. ggd_kanban_column.xml puts the cards in
 *    one, and the drag has to be told about it: Odoo drops its placeholder
 *    straight into .o_kanban_group when the pointer enters a column, which
 *    with the box in place lands outside the scrolled area and, worse, makes
 *    the box itself the element the drop reads as "the card I landed after".
 *
 * 2. Remember a folded column. Odoo folds client-side only - group.toggle()
 *    writes nothing anywhere - so leaving the pipeline and coming back opens
 *    every column again. The choice is kept in localStorage, like the theme's
 *    tone: it is a per-browser display preference, and for a single-operator
 *    CRM that is the right trade and needs no field on res.users.
 *
 * Both are scoped to the pipeline. The fold memory keys on crm.lead so the
 * other boards keep Odoo's behaviour; the placeholder move is a no-op
 * anywhere the box does not exist.
 */

import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { Group } from "@web/model/relational_model/group";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";

const FOLD_MODEL = "crm.lead";

/** One list per model and group-by, so a different grouping starts clean. */
function foldKey(resModel, fieldName) {
    return `ggd_folded_columns:${resModel}:${fieldName}`;
}

function readFolded(resModel, fieldName) {
    try {
        const stored = JSON.parse(localStorage.getItem(foldKey(resModel, fieldName)));
        return new Set(Array.isArray(stored) ? stored : []);
    } catch {
        return new Set();
    }
}

function writeFolded(resModel, fieldName, folded) {
    try {
        localStorage.setItem(foldKey(resModel, fieldName), JSON.stringify([...folded]));
    } catch {
        // private mode or blocked storage: the fold still holds for this page
    }
}

patch(Group.prototype, {
    /**
     * Every way of folding a column ends here - the header's Fold menu and a
     * click on a folded column both call it - so it is the one place the
     * choice has to be written down.
     */
    async toggle() {
        const folding = !this.isFolded;
        const result = await super.toggle(...arguments);
        const { resModel, groupByFieldName } = this.config;
        if (resModel === FOLD_MODEL && groupByFieldName) {
            const folded = readFolded(resModel, groupByFieldName);
            folded[folding ? "add" : "delete"](String(this.value));
            writeFolded(resModel, groupByFieldName, folded);
        }
        return result;
    },
});

patch(KanbanRenderer.prototype, {
    setup() {
        super.setup();
        // Runs when the board arrives and again whenever the set of columns
        // changes, which is the moment the remembered folds have to be put
        // back. Folding a column does not change that set, so unfolding one
        // by hand is not undone on the next render.
        useEffect(
            () => {
                this.ggdRestoreFoldedColumns();
            },
            () => [(this.props.list.groups || []).map((group) => group.id).join("|")]
        );
    },

    ggdRestoreFoldedColumns() {
        const list = this.props.list;
        if (!list.isGrouped || list.resModel !== FOLD_MODEL || !list.groupByField) {
            return;
        }
        const folded = readFolded(list.resModel, list.groupByField.name);
        if (!folded.size) {
            return;
        }
        for (const group of list.groups) {
            if (!group.isFolded && folded.has(String(group.value))) {
                group.toggle();
            }
        }
    },

    /**
     * Odoo appends the drag placeholder to the column element itself. With
     * the cards in a box, that puts it outside the scrolled area, and the
     * drop then walks back from it to the previous sibling - the box - and
     * takes the box's id for a card id. Moving it into the box makes both
     * right again; a folded column keeps a box too (hidden), so a card can
     * still be dropped on one.
     */
    sortRecordGroupEnter(params) {
        const result = super.sortRecordGroupEnter(...arguments);
        const body = params.group.querySelector(":scope > .ggd_col_body");
        const placeholder = params.group.querySelector(":scope > .o_kanban_record");
        if (body && placeholder) {
            body.appendChild(placeholder);
        }
        return result;
    },
});
