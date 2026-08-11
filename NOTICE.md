# Third-party artwork notices

The map-n-flag **code** (pipeline, library, examples) is MIT licensed — see
`LICENSE`. The **artwork** compiled into `src/` comes from two upstream
projects with different terms. Read this before shipping anything.

---

## Flags — lipis/flag-icons

- Source: <https://github.com/lipis/flag-icons>
- License: **MIT** — Copyright (c) 2013 Panayiotis Lipiridis
- Status: ✅ **Unrestricted.** Commercial use is fine.

The flag SVGs were rasterised to 80×60 and reduced to a 16-colour indexed
palette. No other modification.

---

## Map outlines — djaiss/mapsicon

- Source: <https://github.com/djaiss/mapsicon>
- Author: **David Jaiss**
- License: ⚠️ **Custom, not an OSI-approved license.**

The upstream README states, verbatim:

> Do what you want with them as long as you mention me in your project.
> Please don't resell them - I forbid it!

### What this means

✅ **Permitted:** personal, hobby, and educational use — **provided David Jaiss
is credited**. That credit appears in every generated source file, in this
file, and in `README.md`. You should also add it to an about/credits screen in
any application that ships these assets.

❌ **Not permitted:** reselling the artwork, or shipping it in a product you
sell. This clause makes the outlines **unsuitable for commercial use**.

### If you need commercial rights

Replace the outline artwork with [Natural Earth](https://www.naturalearthdata.com/)
`ne_110m_admin_0_countries`, which is in the **public domain** with no
restrictions. Only `load_map()` in `tools/build.py` needs to change — it would
rasterise the polygons instead of loading mapsicon PNGs. Everything downstream
(quantisation, packing, emission, the whole API) is unaffected, and the flags
are MIT so they need no changes at all.

The following countries are absent from mapsicon and therefore have a flag but
no outline: **FM** (Micronesia), **MH** (Marshall Islands), **PS** (Palestine),
**TV** (Tuvalu). Upstream omits them as too small to draw.

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
