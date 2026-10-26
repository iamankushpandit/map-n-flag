# Third-party artwork notices

The map-n-flag **code** (pipeline, library, examples) is MIT licensed — see
`LICENSE`. Most of the **artwork** compiled into `src/` comes from upstream
projects with different terms; the playing cards are drawn by this repo's own
tooling. Read this before shipping anything.

---

## Country flags — lipis/flag-icons

- Source: <https://github.com/lipis/flag-icons>
- License: **MIT** — Copyright (c) 2013 Panayiotis Lipiridis
- Status: ✅ **Unrestricted.** Commercial use is fine.

The flag SVGs were rasterised to 80×60 and reduced to a 16-colour indexed
palette. No other modification.

---

## US state flags — fonttools/region-flags

- Source: <https://github.com/fonttools/region-flags>
- License: ✅ **Public domain.** Downloaded from Wikipedia; when originals
  were copyrighted, the project sourced or drew new public-domain versions.
- Status: ✅ **Unrestricted.** Commercial use is fine.

The flag SVGs were rasterised to 80×60 and reduced to a 16-colour indexed
palette. No other modification.

---

## US state map outlines — Natural Earth

- Source: <https://www.naturalearthdata.com/>
- Dataset: `ne_10m_admin_1_states_provinces`
- License: ✅ **Public domain** (Open Data Commons PDDL).
- Status: ✅ **Unrestricted.** Commercial use is fine.

State outlines were extracted from the Natural Earth GeoJSON, rendered as
alpha-ramp silhouettes, and encoded as 4-bit indexed images. While
no credit is required, a link back to Natural Earth is appreciated.

---

## Playing cards — no third party involved

- Source: [`tools/render_cards.py`](tools/render_cards.py) in this repo.
- License: **MIT**, same as the rest of the code here.
- Status: ✅ **Unrestricted.** Commercial use is fine.

The deck is drawn from vector primitives -- parametric curves for the pips,
stroke paths for the rank glyphs -- with no upstream SVG set and no font
embedded or traced. There is nothing to attribute.

---

## Build-time tooling

These run on the development machine only and are **not** compiled into the
firmware:

| Tool | License |
|---|---|
| [sharp](https://github.com/lovell/sharp) | Apache-2.0 |
| [Pillow](https://python-pillow.org/) | MIT-CMU |
| [NumPy](https://numpy.org/) | BSD-3-Clause |
| [pycountry](https://github.com/pycountry/pycountry) | LGPL-2.1 |

`pycountry` is used only by `tools/gen_country_table.py` to refresh country
names into a generated Python file. It is not required to build the library,
and none of its code is redistributed here.
