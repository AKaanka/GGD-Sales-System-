# Aurora design record, September 2026

The design work behind the Aurora theme (addon 19.0.1.18.0, PR #56), kept
so later UI work starts from what was drawn and decided. Issue #58 carries
the decisions; this folder carries the pictures and the sources.

Every company name in these files is invented sample data.

## Folders

- `mockups/`: the design canvas artboards rendered at 1440×900.
  `aurora-*` is the chosen direction, `tone-*` the two tone alternates that
  shipped as user-selectable tones, `alt-*` the four directions that were
  drawn and not chosen (Ledger, Bento, Noir, Terminal).
- `odoo/`: the running Odoo after the theme landed, same screens, taken
  through headless Chrome on a local stack with sample data.
- `source/`: the artboards as `.dc.html` (plain HTML; open one in a browser
  to see it), `canvas.json` (the canvas layout), and the two Python scripts
  that generated them. `gen.py` holds the Aurora system and the sample data;
  `gen2.py` holds the four alternatives. Both write next to themselves.

The live canvas, with pan, zoom and PNG/PDF export, is linked from #58. It
needs a claude.ai login; these files do not.

## Regenerating

```
cd docs/design/aurora-2026-09/source && python3 gen.py && python3 gen2.py
```

Then open any `.dc.html` in a browser. The `<script src="./support.js">`
line in each file is a hook for the canvas editor and is harmless outside it.

## Gallery

GitHub renders these on the repository page; the issue cannot embed them because the repository is private.

### Chosen: Aurora, as drawn

**Pipeline, dark**

![Pipeline, dark](mockups/aurora-pipeline-dark.jpg)

**Review desk, dark**

![Review desk, dark](mockups/aurora-review-desk-dark.jpg)

**Opportunity, dark**

![Opportunity, dark](mockups/aurora-opportunity-dark.jpg)

**Pipeline, light**

![Pipeline, light](mockups/aurora-pipeline-light.jpg)

### The tones, shipped as user-selectable

**Ember**

![Ember](mockups/tone-ember.jpg)

**Graphite**

![Graphite](mockups/tone-graphite.jpg)

### Shipped: the running Odoo after PR #56

**Pipeline, Aurora dark**

![Pipeline, Aurora dark](odoo/odoo-pipeline-dark.jpg)

**Opportunity with the GGD tab, Aurora dark**

![Opportunity with the GGD tab, Aurora dark](odoo/odoo-opportunity-dark.jpg)

**Review desk, Aurora dark**

![Review desk, Aurora dark](odoo/odoo-review-desk-dark.jpg)

**Pipeline, Aurora light**

![Pipeline, Aurora light](odoo/odoo-pipeline-light.jpg)

**Appearance menu**

![Appearance menu](odoo/odoo-appearance-menu-light.jpg)

**Review desk, Ember light**

![Review desk, Ember light](odoo/odoo-review-desk-ember-light.jpg)

**Opportunity, Graphite dark**

![Opportunity, Graphite dark](odoo/odoo-opportunity-graphite-dark.jpg)

**Discuss, dark**

![Discuss, dark](odoo/odoo-discuss-dark.jpg)

**Settings, dark**

![Settings, dark](odoo/odoo-settings-dark.jpg)

### Not chosen: the four alternatives

**Ledger**

![Ledger](mockups/alt-ledger.jpg)

**Bento**

![Bento](mockups/alt-bento.jpg)

**Noir**

![Noir](mockups/alt-noir.jpg)

**Terminal**

![Terminal](mockups/alt-terminal.jpg)

