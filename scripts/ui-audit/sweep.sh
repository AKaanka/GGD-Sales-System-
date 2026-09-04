#!/bin/bash
# The standard Aurora sweep: seventeen screens, computed-style audit and
# console errors, in a given scheme and tone.
#
#   ./scripts/ui-audit/sweep.sh <session_id> <light|dark> <tone> <outdir> [lead_id]
#
# Get a session id with:
#   curl -s -c - -X POST http://localhost:8069/web/session/authenticate \
#     -H 'Content-Type: application/json' \
#     -d '{"jsonrpc":"2.0","params":{"db":"ggd","login":"<login>","password":"<password>"}}' \
#     -o /dev/null | awk '$6=="session_id"{print $7}'
#
# Use a local database with sample data. Never point this at the stack host.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
sid="${1:?session id}"; scheme="${2:?light|dark}"; tone="${3:?tone}"; out="${4:?outdir}"; lead="${5:-}"
A="@file:$here/audit.js"
pages=(
  "pipeline=/odoo/action-crm.crm_lead_action_pipeline@@$A"
  "desk=/odoo/action-ggd_crm.action_ggd_review_desk@@$A"
  "search=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_searchview_dropdown_toggler').click();"
  "apps=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_navbar_apps_menu button').click();"
  "usermenu=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_user_menu button, .o_user_menu .dropdown-toggle').click();"
  "carddrop=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_dropdown_kanban button').click();"
  "quick=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_kanban_quick_add').click();"
  "modal=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_button_generate_leads').click(); await new Promise(r=>setTimeout(r,1200));"
  "appearance=/odoo/action-crm.crm_lead_action_pipeline@@$A|document.querySelector('.o_ggd_appearance button').click();"
  "discuss=/odoo/discuss@@$A"
  "settings=/odoo/settings@@$A"
  "users=/odoo/action-base.action_res_users@@$A"
  "listview=/odoo/action-crm.crm_lead_action_pipeline?view_type=list@@$A"
  "calendar=/odoo/action-crm.crm_lead_action_pipeline?view_type=calendar@@$A"
  "pivot=/odoo/action-crm.crm_lead_action_pipeline?view_type=pivot@@$A"
  "dragcard=/odoo/action-crm.crm_lead_action_pipeline@@@drag:.o_kanban_group:nth-child(2) .o_kanban_record|.o_kanban_group:nth-child(3) .o_kanban_header"
)
if [ -n "$lead" ]; then
  pages+=("form=/odoo/crm/$lead@@$A|[...document.querySelectorAll('.o_notebook_headers .nav-link')].find(a=>/GGD/.test(a.textContent)).click();")
  pages+=("m2o=/odoo/crm/$lead@@$A|const i=document.querySelector('.o_field_many2one_selection input, .o_input_dropdown input'); i.focus(); i.value='a'; i.dispatchEvent(new Event('input',{bubbles:true}));")
fi
node "$here/odoo-shot.mjs" "$sid" "$scheme" "$tone" "$out" "${pages[@]}"
echo
echo "== findings (B = computed style, filtered for the theme's own accent and popover colours)"
cat "$out"/*.js.txt 2>/dev/null | grep '^B ' | grep -v -E 'rgba\(79, 214, 200|rgb\(79, 214, 200|rgba\(198, 245, 66|rgb\(198, 245, 66|rgba\(240, 163, 92|rgba\(24, 28, 38|rgba\(26, 27, 31|rgba\(32, 26, 22|o_tour_pointer|o_field_color|o_arrow_button.*::before|o_colorlist_item' | sort | uniq -c | sort -rn || true
echo "== console errors (beforeunload lines are the harness leaving a dirty form)"
grep -v -E 'beforeunload|^$' "$out"/*.errors.txt 2>/dev/null || echo "none"
