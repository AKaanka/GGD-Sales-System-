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
| `ggd_ring_field.js` and `.xml` | the `ggd_ring` field widget: a conic-gradient ring for the fit score, 64px on the form, 30px with `options="{'size': 'sm'}"` on kanban cards and list rows. |

The views that use the widgets:

- `views/crm_lead_views.xml`: the status strip above the opportunity title
  (ring, pills, approval line, send key) and the kanban card row (ring,
  industry, pills).
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
