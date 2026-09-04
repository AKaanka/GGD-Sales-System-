# UI audit

Tools that drove the Aurora theme work (#58) and caught what a look at a
screenshot misses: a hover colour, a focus ring, a dragged card, a white
tab bar in dark mode. They run against a **local** Odoo through headless
Chrome and need nothing but Node 22 and a Chrome binary.

## Files

- `odoo-shot.mjs`: the driver. Logs in with a session cookie, opens pages,
  runs a step (evaluate JS, hover, drag, force pseudo-states), and writes a
  screenshot, a DOM outline and the console errors per page. The header
  comment documents every step form.
- `audit.js`: evaluated inside a page. Part A lists Odoo stylesheet rules
  for `:hover`, `:focus`, `:active`, `.show`, drag classes and
  `::before/::after` that still set a literal colour and match an element on
  the page: an inventory of what the theme must override. Part B scans
  computed styles and reports light backgrounds in dark mode, low-contrast
  text, Odoo-palette borders and shadows, and anything in Odoo's purple.
- `sweep.sh`: the standard seventeen-screen run with the audit on each,
  including a real kanban drag. The command to obtain a session id is in
  its header.

## Reading the output

Part A is an inventory, not a defect list: a rule appears whether or not
the theme already wins over it. Part B is the defect list; the sweep
filters the theme's own accent and popover colours out of it. A `B` line
that survives the filter is a surface still on Odoo's paint. The
`::before` on the stage buttons and the colour swatches in the kanban
colour picker are known false positives.

The forced-state audit (`@force:`) diffs computed colours against Odoo's
palette; a few of the theme's greys sit within its tolerance, so treat a
hit as a lead to look at, not a verdict.

## Rules

- Local database only, with invented sample data. Never point this at the
  stack host: the drag step moves records, and the form steps edit them.
- Restart the Odoo service after a change to `ggd_theme.scss` before
  running; the asset bundle is rebuilt on restart.
- One run at a time: the driver binds Chrome's debugging port 9333.
