# The Aurora theme

The CRM does not look like a stock Odoo. Since addon 19.0.1.18.0 the backend
wears one theme, "Aurora": a flat top bar, glass panels over a faint two-corner
glow, Manrope for text and IBM Plex Mono for keys, and a fixed colour language
for outbound state. This page says what it is, how a user changes it, and
where to edit it.

## What a user can change

The sun/moon button at the right of the top bar opens the appearance menu:

- **Scheme**: light or dark.
- **Tone**: Aurora (teal and violet), Ember (amber and coral), or Graphite
  (monochrome with one lime accent).

Both apply immediately, without a reload. They are browser preferences, not
user settings: the scheme lives in the `color_scheme` cookie that
`models/ir_http.py` already reads, the tone in `localStorage` under
`ggd_tone`. A different browser starts from light Aurora.

## The top bar

The bar is Odoo's `NavBar` with two templates extended (`ggd_navbar.xml`)
and a small patch (`ggd_navbar.js`):

- The gradient mark on the left opens the apps menu, where Odoo's grid icon
  was. The wordmark "Growth Desk" replaces the app name; outside the CRM the
  app name follows it in grey, so Settings still says Settings.
- The app's sections are pills, and the one the screen belongs to is lit.
  "Belongs to" is decided from the action on screen, first by action id,
  then by the action path Odoo 18+ puts in the URL (the CRM's own "My
  Pipeline" menu runs a server action, so its id never matches). A page
  opened by a bare action URL has no current app in Odoo, so it shows the
  wordmark alone, as stock Odoo would show nothing.
- The magnifier on the right opens the command palette (Ctrl+K), themed.

## The pipeline board

The board fills the viewport and never scrolls as a page. Every column is
the full height of it - folded or not - and scrolls on its own under a
header that stays put, so a drag never moves a column's title and an empty
stage is still a place to drop a card. Columns are borderless glass, 268 px
wide; folded, a column becomes a 56 px spine with its title running up it
and the count under the title. The gear is always visible.

The header counts records rather than summing revenue (this pipeline is
about people to write to). The count sits in a pill beside the stage name,
which Odoo only prints there when a column has no progress bar; the
pipeline has one, so `ggd_kanban_header.xml` puts the number back - for
`crm.lead` only, because `web.KanbanHeader` is one template for every
kanban in the database.

### The line under the column title

In the design that line is the mix of outbound states of the cards in the
column, in the four status colours. In Odoo the same drawing already
exists, as `<progressbar>`, and it does more than draw: clicking a segment
filters the column down to the records in that state. So the theme stopped
painting over it with an accent gradient and gave it the right field.

That field is `ggd_board_state`: a stored, indexed, computed selection that
collapses qualification, draft, delivery, reply and the review flags into
one of five values, highest urgency first - `stop`, `review`, `wait`, `ok`,
`none`. It exists because `read_progress_bar` groups on a single stored
field in SQL and a segment click is a search on it, and because a card can
be in several states at once and the colour has to say the most urgent.
It is derived and never written.

### The selection bar

Above the columns sits one row of controls. It began (issue #58) as four
chips and grew (issue #67) into the whole of how a salesperson narrows the
board:

`Country ▾  Product group ▾  Company type ▾  More ▾ | Sendable today · Needs
review · Unresolved claim · Replies | N leads · Clear selection · Daily send
cap`

Three rules hold it together.

**Nothing in the bar is a filter of its own.** Every control toggles a
search item that lives in the search view, so a click leaves a facet
behind, the Filters menu shows it ticked, and "Save current search" keeps
it. That is what makes a saved working view an ordinary Odoo favourite
rather than a second, private idea of what a filter is - and it is why the
bar renders over the list as well as the board, where the same selection
has to stay visible while rows are ticked for a bulk action.

**Odoo's own AND/OR is the AND/OR.** Each picker drives one search-view
*field*, and `SearchModel._getFieldDomain` ORs the values of one field
while ANDing different fields. Two countries mean either; a country and a
product group mean both. No domain is written in the component. A lead in
two product groups matches once, because a domain returns records rather
than rows - which is also why the product group is deliberately not offered
as a group-by.

**The numbers describe what is on screen.** The counts come from
`crm.lead.ggd_board_chip_counts(domain)`, called with the active search
domain, so a chip counts inside the selection rather than across the
database. Before #67 it was the second, and the bar contradicted the board
the moment a group was picked. `matching` is the same count for the
selection itself, printed beside the facets.

The daily send cap is the exception, and it is printed apart from the chips
and labelled *system-wide*. It limits send claims across the whole
installation per 24 hours; sitting on the Sendable chip as `3 / 20` it read
like the selected group's allowance, which it never was.

`Clear selection` deactivates the groups this bar set and nothing else, so
the pipeline's default `My Pipeline` scope survives it.

Two things to keep in step when editing: the four chip domains exist both in
`GGD_BOARD_CHIP_DOMAINS` and in the search view's `ggd_chip_*` filters, and
the picker fields and named filters are matched by name between
`ggd_quick_filters.js` and `views/crm_lead_views.xml`.

One OWL detail worth knowing before touching the template: a Dropdown's
content slot is rendered in a popover that captures the parent's render
context when it opens, so a `t-foreach` **in the parent** whose loop
variable is used **inside** the slot goes stale. The bar renders the
pickers that way and gets away with it only because the component re-renders
on every `searchModel` update; if that changes, move the loop inside the
slot or give each picker a component of its own.

### The card

The card is the design's: the opportunity, then city and industry as a
subtitle, then one row with the fit score on the left and the outbound
state on the right. Three things Odoo puts on a CRM card are gone -
priority stars, because the column is ordered by hand; the assignee
avatar, because there is one user; the rotting clock, because the review
desk already asks that question. The scheduled activity moved into the pill
row rather than being dropped, and the CRM tags moved there with it. The
card that is waiting on a person is lit with the accent, as the design
lights it; the theme finds it with `:has()` on a marker the view renders
when `ggd_board_state` is `wait`.

The revenue line is hidden by the theme rather than removed from the
template, because the CRM's forecast kanban inherits the same template and
has an xpath of its own on it.

Cards can be reordered by hand inside a column. Stock Odoo refuses this
on `crm.lead`, which has no `sequence` field and orders by priority; the
addon adds `sequence` (default 10, set by dragging) and makes the kanban
sort by it first. The model's own order is untouched, so the list view and
searches still order by priority as the CRM ships them.

## The control panel

The design's toolbar reads left to right: breadcrumb and title, then all
the way over, the search, the view switcher, and the primary button. Odoo's
order is the reverse and its rows are top-aligned, so the search sat a few
pixels above the title. Both are fixed in CSS, not in a template: the
control panel is one component for every view in the database, and this is
a layout, not a structure. Odoo nests the create buttons inside the
breadcrumb block, so that block is dissolved with `display: contents` and
the five parts are ordered as flex items of one row. It applies from
Odoo's `lg` breakpoint up; below it the panel wraps onto three rows and
keeps Odoo's own order.

## The fit score

Two shapes, both the design's. On the opportunity form it is a 64 px ring,
a conic gradient filled to the value. On a kanban card it is the number
followed by a 46x5 bar, because a ring at card scale reads as an avatar and
the row has to stay one line high. One widget, `ggd_ring`, with
`options="{'variant': 'bar'}"` selecting the second.

## Sizes, weights and the type scale

The design fixes one type scale - Manrope at 13 px on a 1.45 line, against
Odoo's 14 px - and one set of metrics for every control. They live as
custom properties in the `--ggd-*` metrics block at the top of
`ggd_theme.scss`: button and chip and pill heights, input padding, radii,
the page margin, the column width, the gap between panels. A structural
rule reads one of those rather than repeating a number, so a change to the
design is a change to that block.

## Icons

The design draws round-capped 2 px strokes on a 24 unit grid; Odoo ships
Font Awesome, whose glyphs are solid and heavier. Only the icons the
design actually draws are replaced (issue #58). Where the markup is ours -
the search button, the appearance menu, the Fetch mail button, the systray
activity bell, the chips - the glyph is an inline SVG from
`ggd_icons.xml`. Where it is an Odoo `<i>` carrying an icon-font class with
no room for a child - the kanban and list view switchers, the column plus -
the glyph is blanked and the design's outline is painted through a CSS mask
in the current colour.

## The colour language

Status pills use the same four colours everywhere: kanban cards, the review
desk, and the strip at the top of an opportunity.

| Colour | Meaning | Where it appears |
| --- | --- | --- |
| teal (`--ggd-ok`) | done, accepted | draft approved or sent, delivery accepted, reply interested |
| amber (`--ggd-wait`) | waiting on a person | draft ready for review |
| violet (`--ggd-review`) | the automation refused to decide | qualification needs review, reply unclear or an objection |
| rose (`--ggd-stop`) | stop and look | send claimed with unknown outcome, bounced, unsubscribe, Do not contact |

The tones change the accent (buttons, focus rings, the fit ring) and the
temperature of the greys. They do not change the four status colours, so a
rose pill means the same thing in every tone.

## Where things live

All of it is in `odoo/addons/ggd_crm/static/src/`:

| File | What it does |
| --- | --- |
| `ggd_theme.scss` | the whole theme. Palette first (custom properties per scheme and tone), then overrides grouped by area: navbar, dropdowns, buttons, control panel, kanban, list, form, chatter, badges, ring, strip. |
| `ggd_fonts.scss` and `fonts/` | `@font-face` for the bundled Manrope and IBM Plex Mono, latin and latin-ext subsets. Nothing is fetched from Google at runtime. |
| `appearance_menu.js` and `.xml` | the systray menu. Sets `data-ggd-scheme` and `data-ggd-tone` on `<html>` at module load and on every change. |
| `ggd_navbar.js` and `.xml` | the top bar: mark, wordmark, lit section, search button. |
| `ggd_ring_field.js` and `.xml` | the `ggd_ring` field widget: a conic-gradient ring for the fit score, 64px on the form and 30px with `options="{'size': 'sm'}"` in list rows, or the number and a 46x5 bar with `options="{'variant': 'bar'}"` on kanban cards. |
| `ggd_icons.xml` | the design's SVG icons, as QWeb templates the other files `t-call`. |
| `ggd_quick_filters.js` and `.xml` | the selection bar above the pipeline: the country, product-group and company-type pickers, the More menu, the four state chips, the result count, Clear selection and the send-cap label, plus the `web.KanbanView` and `web.ListView` extensions that place it. |
| `ggd_kanban_header.xml` | the card count beside the column title, for `crm.lead` only. |

The views that use the widgets:

- `views/crm_lead_views.xml`: the status strip above the opportunity title
  (ring, pills, approval line, send key), the kanban card (subtitle, score
  bar, pills), the `ggd_board_state` progress bar on the column header, the
  four `ggd_chip_*` filters behind the state chips, and the search fields and
  named filters behind the selection bar's pickers and More menu.
- `views/ggd_lead_bulk_action_views.xml`: the three bulk-action dialogs. They
  are ordinary Odoo wizard forms and carry no theme of their own; the alert
  blocks and the footer are Bootstrap classes the theme already paints.
- `views/ggd_review_desk_views.xml`: badge widgets with `decoration-*`
  attributes on the status columns.

## How it is built, and the two rules that keep it working

Odoo 19 Community compiles its Bootstrap to literal colours: there are no
`--bs-*` custom properties to redefine, and many Odoo rules carry
`!important`. So the theme defines its own custom properties on `:root`,
switches them by the two `<html>` attributes, and overrides Odoo's classes
with rules of equal or higher weight. Two consequences for anyone editing it:

1. **Colours go in the palette block only.** A structural rule never names a
   colour; it uses `var(--ggd-...)`. Add a tone by adding one light block and
   one dark block of custom properties, and one entry to `TONES` in
   `appearance_menu.js`.
2. **Write `RGBA(var(--ggd-x-rgb), 0.2)` in capitals.** Odoo's SCSS compiler
   is libsass, which tries to evaluate lowercase `rgba()` and fails on a
   `var()` argument. The uppercase spelling passes through untouched;
   Bootstrap relies on the same trick.

Selectors were taken from the DOM of the running Odoo, not from memory. When
an Odoo upgrade renames a class, the symptom is a surface that falls back to
Odoo's own paint (usually white in dark mode). The fix is to find the new
class in the browser and add it to the matching group.

## Checking it

After a change to `ggd_theme.scss`, restart the Odoo service so the asset
bundle is rebuilt, then look at four screens in both schemes: the pipeline
kanban, the review desk, an opportunity with the GGD Intelligence tab open,
and the search dropdown. In dark mode, anything white is a missed selector.
A dark and a light screenshot of each screen are the evidence a pull request
should carry.

Two surfaces are easy to forget because they are not GGD screens and only
appear on a click: the calendar view, whose FullCalendar paints from its own
`--fc-*` variables rather than from Bootstrap's, and the tooltips, which
render in the overlay container outside `.o_web_client` and so are reached by
none of the rules scoped to it. Both have a block of their own in the theme.

That the stylesheet compiles can be checked without logging in - but only
after the cached bundle is cleared. Odoo stores the compiled bundle as an
`ir.attachment` and does not notice that a file on disk changed, so a plain
restart serves the old CSS and every grep below passes on stale content:

```
docker compose exec -T odoo-db psql -U odoo -d ggd \
  -c "delete from ir_attachment where url like '/web/assets/%';"
docker compose restart odoo
curl -sL -o /tmp/b.css "http://localhost:8069/web/assets/any/web.assets_backend.min.css"
grep -c ggd_quick_filters /tmp/b.css
```

The route is public and rebuilds the bundle on demand, so a SCSS error shows
up as a failed request and a traceback in `docker compose logs odoo`. The
deleted rows are a cache and are written again on the first request.
