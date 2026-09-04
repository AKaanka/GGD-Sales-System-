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
