# map-n-flag

Country flags and map silhouettes for **195 countries** plus **51 US states**
(+ DC), baked into flash as plain C++ arrays for the ESP32. No runtime SVG
parsing, no SD card, no external asset loading — everything is `const` data in
`.rodata`.

Built for a 320×240 ESP32 "Cheap Yellow Display" (ILI9341, 4 MB flash, no PSRAM),
but there is nothing board-specific in the library.

- **Zero RAM.** `.bss` and `.data` are both 0 bytes — verified with `xtensa-esp32-elf-size`.
- **No LVGL required.** The core has no dependency beyond `stdint.h`. Draw with
  TFT_eSPI, LovyanGFX, or anything else. LVGL v8/v9 support is an optional header.
- **1.09 MiB** of flash for all 195 flags *and* 191 outlines.
- **280 KiB** more for 51 US state flags and outlines (opt-in, both commercially safe).

```cpp
#include "map_n_flag.h"

const mnf_img_t *flag = mnf_flag("FR");   // 80x60 indexed image
const mnf_img_t *map  = mnf_map("FR");    // silhouette, same ISO code
const char      *name = mnf_name("FR");   // "France"

// US states -- same image format, separate lookup
const mnf_img_t *sf = mnf_state_flag("CA");   // California flag
const mnf_img_t *sm = mnf_state_map("CA");    // California outline
const char      *sn = mnf_state_name("CA");   // "California"
```

---

## Install

### PlatformIO (recommended)

```ini
[env:app]
platform = espressif32
board = esp32dev
framework = arduino
board_build.partitions = huge_app.csv
lib_deps =
    bodmer/TFT_eSPI@^2.5.43
    https://github.com/iamankushpandit/map-n-flag.git
```

### Arduino IDE

Download the repo as a ZIP and use **Sketch → Include Library → Add .ZIP
Library**, or copy `src/` into your sketch folder.

### ⚠️ You must change the partition scheme

A 4 MB ESP32 on the Arduino **default** partition gives the app only **1.31 MB**
— less than this library alone. Use **"Huge APP (3MB No OTA/1MB SPIFFS)"**, or
in PlatformIO `board_build.partitions = huge_app.csv`.

---

## How to Use

This section walks you through the typical steps to get map-n-flag running on
your ESP32, from installation to drawing your first flag.

### 1. Install the library

Follow the [Install](#install) instructions above — PlatformIO is recommended.
Make sure you set the partition scheme to `huge_app.csv`.

### 2. Include the header and look up a country

```cpp
#include "map_n_flag.h"

// Lookup by ISO 3166-1 alpha-2 code (case-insensitive)
const mnf_img_t *flag = mnf_flag("DE");   // Germany flag (80×60)
const mnf_img_t *map  = mnf_map("DE");    // Germany outline silhouette
const char      *name = mnf_name("DE");   // "Germany"
```

All lookups return `NULL` for unknown codes, so always check the pointer before
drawing. Four countries (FM, MH, PS, TV) have a flag but no outline — use
`mnf_has_both()` to filter them when you need both.

### 3. Draw with TFT_eSPI (no LVGL)

Decode one row at a time straight from flash — no framebuffer, ~192 bytes of
scratch:

```cpp
#include <TFT_eSPI.h>
#include "map_n_flag.h"

TFT_eSPI tft;
static uint16_t row[96];

void draw_flag(const mnf_img_t *img, int16_t x, int16_t y) {
    if (img == NULL) return;
    tft.startWrite();
    for (uint16_t yy = 0; yy < img->h; yy++) {
        mnf_row_rgb565(img, yy, row, TFT_WHITE);
        tft.setAddrWindow(x, y + yy, img->w, 1);
        tft.pushPixels(row, img->w);
    }
    tft.endWrite();
}

void setup() {
    tft.init();
    tft.setRotation(1);
    tft.fillScreen(TFT_WHITE);
    draw_flag(mnf_flag("JP"), 30, 90);   // draw Japan's flag
}
```

Outline silhouettes store a 16-step alpha ramp — recolour them at draw time
with `mnf_row_rgb565_tint()`:

```cpp
// Draw Germany's outline in navy blue
for (uint16_t yy = 0; yy < map->h; yy++) {
    mnf_row_rgb565_tint(map, yy, row, TFT_WHITE,
                        tft.color565(0x1E, 0x3A, 0x8A));
    tft.setAddrWindow(200, 90 + yy, map->w, 1);
    tft.pushPixels(row, map->w);
}
```

See the complete sketch in [`examples/TftEspiDemo`](examples/TftEspiDemo/TftEspiDemo.ino).

### 4. Draw with LVGL (optional)

Include the optional adapter header. Each `mnf_lv_dsc_t` slot must stay alive
as long as the widget is visible — one slot per displayed image.

```cpp
#include "map_n_flag_lvgl.h"

static mnf_lv_dsc_t flag_slot;

lv_obj_t *img = lv_img_create(lv_scr_act());
lv_img_set_src(img, mnf_lv_bind(&flag_slot, mnf_flag("JP")));
lv_obj_center(img);
```

See the complete sketch in [`examples/LvglDemo`](examples/LvglDemo/LvglDemo.ino).

### 5. Iterate over all countries

```cpp
for (size_t i = 0; i < mnf_count(); i++) {
    const mnf_country_t *c = mnf_at(i);   // sorted by ISO code
    if (!mnf_has_both(c->iso2)) continue; // skip the 4 without an outline
    // use c->iso2, c->name, c->flag, c->map
}
```

### 6. Use US state assets (opt-in)

The state API mirrors the country API, keyed by 2-letter USPS abbreviation:

```cpp
const mnf_img_t *sf = mnf_state_flag("CA");   // California flag
const mnf_img_t *sm = mnf_state_map("CA");    // California outline
const char      *sn = mnf_state_name("CA");   // "California"
```

US state assets are commercially safe — see [Licensing](#licensing) for details.

---

## API

One header, thirteen functions, two structs. Lookup is a binary search over a
sorted table — no allocation, no init call, safe to use before any display setup.

```cpp
// --- lookup -------------------------------------------------------------
size_t               mnf_count(void);              // 195
const mnf_country_t *mnf_at(size_t index);         // sorted by ISO code
const mnf_country_t *mnf_find(const char *iso2);   // "FR" or "fr"
const mnf_img_t     *mnf_flag(const char *iso2);   // NULL if unknown
const mnf_img_t     *mnf_map(const char *iso2);    // NULL if unknown/absent
const char          *mnf_name(const char *iso2);   // "France"
bool                 mnf_has_both(const char *iso2);

// --- pixel access, for drawing without LVGL -----------------------------
uint8_t  mnf_index_at(const mnf_img_t *img, uint16_t x, uint16_t y);
uint32_t mnf_palette_argb(const mnf_img_t *img, uint8_t index);
uint32_t mnf_pixel_argb(const mnf_img_t *img, uint16_t x, uint16_t y);
uint16_t mnf_rgb565(uint8_t r, uint8_t g, uint8_t b);
void     mnf_row_rgb565(const mnf_img_t *img, uint16_t y, uint16_t *out, uint16_t bg565);
void     mnf_row_rgb565_tint(const mnf_img_t *img, uint16_t y, uint16_t *out,
                             uint16_t bg565, uint16_t fg565);
```

```cpp
typedef struct {
    uint16_t w;
    uint16_t h;
    const uint8_t *data;      // palette + 4bpp pixels
} mnf_img_t;

typedef struct {
    const char *iso2;         // "FR"
    const char *name;         // "France" (ASCII, no diacritics)
    const mnf_img_t *flag;    // NULL if not generated
    const mnf_img_t *map;     // NULL if not generated
} mnf_country_t;
```

Flags and outlines share the same ISO key, so pairing them for a "which flag
matches this outline?" mode is two calls with one string.

### US state API

The state API mirrors the country API, keyed by 2-letter USPS abbreviation.
All functions return `NULL`/`0`/`false` if `GENERATE_STATES` was off at build time.

```cpp
// --- US state lookup (parallel to country API) --------------------------
size_t               mnf_state_count(void);             // 51
const mnf_state_t   *mnf_state_at(size_t index);        // sorted by abbreviation
const mnf_state_t   *mnf_state_find(const char *st);    // "CA" or "ca"
const mnf_img_t     *mnf_state_flag(const char *st);    // NULL if unknown
const mnf_img_t     *mnf_state_map(const char *st);     // NULL if unknown/absent
const char          *mnf_state_name(const char *st);    // "California"
bool                 mnf_state_has_both(const char *st);
```

`mnf_state_t` is a typedef for `mnf_country_t` — same struct layout, so all
pixel access functions (`mnf_row_rgb565`, `mnf_row_rgb565_tint`, etc.) work
identically with state images.

### Drawing with TFT_eSPI (no LVGL)

Decode one row at a time straight from flash — no framebuffer, ~192 bytes of
scratch:

```cpp
static uint16_t row[96];

void draw_image(const mnf_img_t *img, int16_t x, int16_t y, uint16_t bg) {
    tft.startWrite();
    for (uint16_t yy = 0; yy < img->h; yy++) {
        mnf_row_rgb565(img, yy, row, bg);
        tft.setAddrWindow(x, y + yy, img->w, 1);
        tft.pushPixels(row, img->w);
    }
    tft.endWrite();
}

draw_image(mnf_flag("FR"), 30, 40, TFT_WHITE);
```

Outlines store a 16-step alpha ramp, so `mnf_row_rgb565_tint()` recolours them
at draw time without regenerating anything:

```cpp
mnf_row_rgb565_tint(img, yy, row, TFT_WHITE, tft.color565(0x1E, 0x3A, 0x8A));
```

Full sketch: [`examples/TftEspiDemo`](examples/TftEspiDemo/TftEspiDemo.ino).

### Drawing with LVGL (optional)

The bytes are already exactly what LVGL expects for a 4-bit indexed image, so
the adapter only fills in a descriptor — it copies no pixels and allocates
nothing. Works on v8 and v9.

```cpp
#include "map_n_flag_lvgl.h"

static mnf_lv_dsc_t flag_slot;    // must outlive the widget
lv_img_set_src(img, mnf_lv_bind(&flag_slot, mnf_flag("FR")));
```

Full sketch: [`examples/LvglDemo`](examples/LvglDemo/LvglDemo.ino).

### ⚠️ Stored size == displayed size (don't call `lv_img_set_zoom`)

Indexed images **cannot be scaled at runtime on LVGL v8**. Its decoder builds a
small palette in RAM and streams pixels from flash line by line — it never
populates `img_data`, and in `lv_draw_img.c` that line-by-line branch ignores
`zoom` and `angle` entirely. `lv_img_set_zoom()` **silently does nothing**.

That's the trade that makes these images cost 0 bytes of RAM. To show a bigger
flag, raise `FLAG_W`/`FLAG_H` and regenerate:

| Flag size | Per image | ×195 | On a 320×240 screen |
|---|---|---|---|
| 64×48 | 1,600 B | 305 KiB | small |
| **80×60** | **2,464 B** | **469 KiB** | **current — a quarter of screen width** |
| 112×84 | 4,768 B | 908 KiB | comfortable |
| 120×90 | 5,464 B | 1,040 KiB | prominent |
| 160×120 | 9,664 B | 1,840 KiB | half the screen |

If you draw with TFT_eSPI instead, you can scale however you like — the
constraint is LVGL's decoder, not the data.

---

## Flash footprint

Measured with `xtensa-esp32-elf-size` on compiled objects, not estimated.

### Countries

| | Count | Flash |
|---|---|---|
| Country flags @ 80×60 | 195 | 469.2 KiB |
| Country outlines @ ≤96 px | 191 | 642.7 KiB |
| **Country total** | **386** | **1,112 KiB (1.09 MiB)** |

### US states (opt-in)

| | Count | Flash |
|---|---|---|
| State flags @ 80×60 | 51 | 122.7 KiB |
| State outlines @ ≤96 px | 51 | 157.9 KiB |
| **State total** | **102** | **280.6 KiB (0.27 MiB)** |

| | Flash |
|---|---|
| Code (`.text`) | ~1.5 KiB |
| **RAM (`.bss` + `.data`)** | **0 bytes** |

Four countries have a flag but no outline — mapsicon omits them as too small to
draw: **FM, MH, PS, TV**. Their `map` pointer is `NULL`; use `mnf_has_both()`
to skip them in paired modes.

---

### ⚠️ Commercial use: turn the country outlines off

The **country** outline artwork (mapsicon) forbids resale, and **not using it is
not enough** — the generated `mnf_table.cpp` references every outline, so the
data stays linked into any firmware that includes this library. To ship
something you sell:

```python
# tools/config.py
GENERATE_MAPS = False
```

That emits no outline arrays, NULLs every `map` pointer, and drops the build
from 1.11 MiB to **469 KiB** — leaving only the MIT-licensed flags. `mnf_map()`
then returns `NULL` for every country, so guard with `mnf_has_both()` or check
the pointer.

**US state assets are commercially safe.** State flags come from
fonttools/region-flags (public domain) and state outlines from Natural Earth
(public domain). `GENERATE_STATES = True` is fine in commercial firmware.

---

## Regenerating

The library is generated by an offline pipeline. You only need this if you want
a different resolution or country set.

```bash
pip install -r requirements.txt
npm install
python tools/fetch_sources.py     # shallow-clones the artwork repos
python tools/build.py             # regenerates src/
python tools/verify.py            # decodes it all back and renders a check sheet
python tools/export_previews.py   # rebuilds the gallery below
```

Rasterisation uses `sharp`, whose prebuilt Windows binary bundles librsvg, so
there is no Cairo/GTK install to fight with.

Size a change before committing to it:

```bash
python tools/build.py --report --scope curated
```

### Tuning

Everything adjustable lives in [`tools/config.py`](tools/config.py):

| Setting | Default | Effect |
|---|---|---|
| `SCOPE` | `"un195"` | `"all"` (~249), `"un195"` (195), `"curated"` (~62) |
| `FLAG_W` / `FLAG_H` | `80` / `60` | Flag resolution |
| `MAP_BOX` | `96` | Max outline dimension |
| `MAP_INK` | navy | Baked silhouette colour (overridable at draw time) |
| `TU_SPLIT` | `4` | Number of generated `.cpp` files |
| `GENERATE_STATES` | `True` | Include US state flags and maps |
| `GENERATE_STATE_MAPS` | `True` | Include state outline maps |

| Scope | Countries | Flags | Maps | Total |
|---|---|---|---|---|
| `all` | 249 | 599.2 KiB | 804.8 KiB | 1.37 MiB |
| `un195` | 195 | 469.2 KiB | 642.7 KiB | **1.09 MiB** ← current |
| `curated` | 62 | 149.2 KiB | 200.6 KiB | 0.34 MiB |

US states add ~280 KiB (122.7 KiB flags + 157.9 KiB maps). Set
`GENERATE_STATES = False` to exclude them entirely.

---

## Design notes

**Image format.** Every image is 4-bit indexed:

```
[16 palette entries × 4 bytes: B, G, R, A][4bpp pixel rows]
```

Rows are padded to whole bytes (`stride = (w + 1) / 2`), and the **leftmost
pixel of each pair is the high nibble**. That is byte-for-byte what LVGL v8 and
v9 both expect — verified against `lv_img_buf.c` and `lv_bin_decoder.c`, where
both compute `shift = 4 - 4 * (x & 1)`.

**Why 80×60 flags.** Measured, not guessed. At 64×48 the US stripes alias into
moiré; at 80×60 they resolve cleanly and India's chakra and Korea's trigrams
survive. 96×72 costs 43% more flash and buys almost nothing, because the
emblem-heavy flags (Mexico, Portugal, Ecuador) are illegible at every size in
this range — and you identify those by colour layout anyway.

**Why 16 colours is enough.** Flags are flat colour blocks. Across all 249,
quantising to a per-flag 16-entry palette gives a mean RGB error of **1.4 out of
a possible 441**. A per-image palette costs 64 bytes and beats any shared one.

**Why indexed and not RGB565.** 4 bpp instead of 16 is ~4× smaller. It also
sidesteps the RGB565 byte-swap problem that bites CYD users, since the palette
is stored as 32-bit ARGB regardless of display endianness.

**Why outlines are indexed too, not `A4`.** A 4-bit alpha mask is the obvious
choice, but LVGL v9 lists `A1`/`A2`/`A4` under *"formats not supported by
software renderer"* — they are GPU-only, and the CYD has no GPU. An `A4` map
would render on v8 and silently break on v9. So outlines use `I4` with a
palette that is a 16-step alpha ramp of one colour: same 4 bpp, plus 64 bytes,
and it renders everywhere. It also makes runtime recolouring trivial.

**Non-rectangular flags.** Nepal's flag is a double pennant. Rather than
flatten it onto a white box, palette slot 0 is reserved as fully transparent
whenever a flag has transparent pixels, so it composites over any background.

**Outline cropping.** Each silhouette is cropped to its tight bounding box
before scaling to fit `MAP_BOX`. Chile becomes ~17×96 instead of a mostly-empty
96×96. Read `img->w` / `img->h` for real dimensions; `MNF_MAP_BOX` is only the
maximum.

Note that mapsicon normalises **each country to fill its own frame**, so the
silhouettes carry no relative-size information — Vatican City and Russia are
drawn at the same scale. That is the right call for recognisability at 96 px,
but don't build a "which country is bigger?" mode on this data.

---

## Licensing

The **pipeline and library code** in this repo are MIT (see `LICENSE`).
The **artwork** comes from two upstream projects:

| Asset set | Source | License | Commercial? |
|---|---|---|---|
| Country flags | [lipis/flag-icons](https://github.com/lipis/flag-icons) | **MIT** | ✅ Yes |
| Country outlines | [djaiss/mapsicon](https://github.com/djaiss/mapsicon) | ⚠️ **Custom** | ❌ No resale |
| US state flags | [fonttools/region-flags](https://github.com/fonttools/region-flags) | **Public domain** | ✅ Yes |
| US state outlines | [Natural Earth](https://www.naturalearthdata.com/) | **Public domain** | ✅ Yes |

mapsicon (country outlines) has no standard license. Its README states, verbatim:

> Do what you want with them as long as you mention me in your project.
> Please don't resell them - I forbid it!

**Fine for a personal or hobby project, provided you credit David Jaiss** — the
credit is in every generated file, in `NOTICE.md`, and here. Please also put it
on an about/credits screen.

**It is not usable in anything you sell.** If this ever becomes commercial, the
outline artwork must be replaced. The drop-in replacement is
[Natural Earth](https://www.naturalearthdata.com/) `admin_0_countries` (public
domain), which touches only `load_map()` in `tools/build.py`. The flags are MIT
and need no changes either way.

**US state assets are commercially safe.** Both the state flags (public domain
from Wikipedia) and state outlines (Natural Earth, public domain) can be used
in commercial products without restriction.

---

## Gallery

<!-- GALLERY:START -->

All 195 countries in the current build (`SCOPE = "un195"`). Flags are 80x60; outlines are cropped to their own bounding box and shown centred in a 96x96 square. These PNGs are decoded from the generated C arrays, so they are exactly what the device draws.

| Code | Country | Flag | Outline |
|:----:|:--------|:----:|:-------:|
| **AD** | Andorra | <img src="docs/previews/flags/AD.png" width="80" alt="Flag of Andorra"> | — |
| **AE** | United Arab Emirates | <img src="docs/previews/flags/AE.png" width="80" alt="Flag of United Arab Emirates"> | — |
| **AF** | Afghanistan | <img src="docs/previews/flags/AF.png" width="80" alt="Flag of Afghanistan"> | — |
| **AG** | Antigua and Barbuda | <img src="docs/previews/flags/AG.png" width="80" alt="Flag of Antigua and Barbuda"> | — |
| **AL** | Albania | <img src="docs/previews/flags/AL.png" width="80" alt="Flag of Albania"> | — |
| **AM** | Armenia | <img src="docs/previews/flags/AM.png" width="80" alt="Flag of Armenia"> | — |
| **AO** | Angola | <img src="docs/previews/flags/AO.png" width="80" alt="Flag of Angola"> | — |
| **AR** | Argentina | <img src="docs/previews/flags/AR.png" width="80" alt="Flag of Argentina"> | — |
| **AT** | Austria | <img src="docs/previews/flags/AT.png" width="80" alt="Flag of Austria"> | — |
| **AU** | Australia | <img src="docs/previews/flags/AU.png" width="80" alt="Flag of Australia"> | — |
| **AZ** | Azerbaijan | <img src="docs/previews/flags/AZ.png" width="80" alt="Flag of Azerbaijan"> | — |
| **BA** | Bosnia and Herzegovina | <img src="docs/previews/flags/BA.png" width="80" alt="Flag of Bosnia and Herzegovina"> | — |
| **BB** | Barbados | <img src="docs/previews/flags/BB.png" width="80" alt="Flag of Barbados"> | — |
| **BD** | Bangladesh | <img src="docs/previews/flags/BD.png" width="80" alt="Flag of Bangladesh"> | — |
| **BE** | Belgium | <img src="docs/previews/flags/BE.png" width="80" alt="Flag of Belgium"> | — |
| **BF** | Burkina Faso | <img src="docs/previews/flags/BF.png" width="80" alt="Flag of Burkina Faso"> | — |
| **BG** | Bulgaria | <img src="docs/previews/flags/BG.png" width="80" alt="Flag of Bulgaria"> | — |
| **BH** | Bahrain | <img src="docs/previews/flags/BH.png" width="80" alt="Flag of Bahrain"> | — |
| **BI** | Burundi | <img src="docs/previews/flags/BI.png" width="80" alt="Flag of Burundi"> | — |
| **BJ** | Benin | <img src="docs/previews/flags/BJ.png" width="80" alt="Flag of Benin"> | — |
| **BN** | Brunei | <img src="docs/previews/flags/BN.png" width="80" alt="Flag of Brunei"> | — |
| **BO** | Bolivia | <img src="docs/previews/flags/BO.png" width="80" alt="Flag of Bolivia"> | — |
| **BR** | Brazil | <img src="docs/previews/flags/BR.png" width="80" alt="Flag of Brazil"> | — |
| **BS** | Bahamas | <img src="docs/previews/flags/BS.png" width="80" alt="Flag of Bahamas"> | — |
| **BT** | Bhutan | <img src="docs/previews/flags/BT.png" width="80" alt="Flag of Bhutan"> | — |
| **BW** | Botswana | <img src="docs/previews/flags/BW.png" width="80" alt="Flag of Botswana"> | — |
| **BY** | Belarus | <img src="docs/previews/flags/BY.png" width="80" alt="Flag of Belarus"> | — |
| **BZ** | Belize | <img src="docs/previews/flags/BZ.png" width="80" alt="Flag of Belize"> | — |
| **CA** | Canada | <img src="docs/previews/flags/CA.png" width="80" alt="Flag of Canada"> | — |
| **CD** | DR Congo | <img src="docs/previews/flags/CD.png" width="80" alt="Flag of DR Congo"> | — |
| **CF** | Central African Republic | <img src="docs/previews/flags/CF.png" width="80" alt="Flag of Central African Republic"> | — |
| **CG** | Congo | <img src="docs/previews/flags/CG.png" width="80" alt="Flag of Congo"> | — |
| **CH** | Switzerland | <img src="docs/previews/flags/CH.png" width="80" alt="Flag of Switzerland"> | — |
| **CI** | Ivory Coast | <img src="docs/previews/flags/CI.png" width="80" alt="Flag of Ivory Coast"> | — |
| **CL** | Chile | <img src="docs/previews/flags/CL.png" width="80" alt="Flag of Chile"> | — |
| **CM** | Cameroon | <img src="docs/previews/flags/CM.png" width="80" alt="Flag of Cameroon"> | — |
| **CN** | China | <img src="docs/previews/flags/CN.png" width="80" alt="Flag of China"> | — |
| **CO** | Colombia | <img src="docs/previews/flags/CO.png" width="80" alt="Flag of Colombia"> | — |
| **CR** | Costa Rica | <img src="docs/previews/flags/CR.png" width="80" alt="Flag of Costa Rica"> | — |
| **CU** | Cuba | <img src="docs/previews/flags/CU.png" width="80" alt="Flag of Cuba"> | — |
| **CV** | Cape Verde | <img src="docs/previews/flags/CV.png" width="80" alt="Flag of Cape Verde"> | — |
| **CY** | Cyprus | <img src="docs/previews/flags/CY.png" width="80" alt="Flag of Cyprus"> | — |
| **CZ** | Czechia | <img src="docs/previews/flags/CZ.png" width="80" alt="Flag of Czechia"> | — |
| **DE** | Germany | <img src="docs/previews/flags/DE.png" width="80" alt="Flag of Germany"> | — |
| **DJ** | Djibouti | <img src="docs/previews/flags/DJ.png" width="80" alt="Flag of Djibouti"> | — |
| **DK** | Denmark | <img src="docs/previews/flags/DK.png" width="80" alt="Flag of Denmark"> | — |
| **DM** | Dominica | <img src="docs/previews/flags/DM.png" width="80" alt="Flag of Dominica"> | — |
| **DO** | Dominican Republic | <img src="docs/previews/flags/DO.png" width="80" alt="Flag of Dominican Republic"> | — |
| **DZ** | Algeria | <img src="docs/previews/flags/DZ.png" width="80" alt="Flag of Algeria"> | — |
| **EC** | Ecuador | <img src="docs/previews/flags/EC.png" width="80" alt="Flag of Ecuador"> | — |
| **EE** | Estonia | <img src="docs/previews/flags/EE.png" width="80" alt="Flag of Estonia"> | — |
| **EG** | Egypt | <img src="docs/previews/flags/EG.png" width="80" alt="Flag of Egypt"> | — |
| **ER** | Eritrea | <img src="docs/previews/flags/ER.png" width="80" alt="Flag of Eritrea"> | — |
| **ES** | Spain | <img src="docs/previews/flags/ES.png" width="80" alt="Flag of Spain"> | — |
| **ET** | Ethiopia | <img src="docs/previews/flags/ET.png" width="80" alt="Flag of Ethiopia"> | — |
| **FI** | Finland | <img src="docs/previews/flags/FI.png" width="80" alt="Flag of Finland"> | — |
| **FJ** | Fiji | <img src="docs/previews/flags/FJ.png" width="80" alt="Flag of Fiji"> | — |
| **FM** | Micronesia | <img src="docs/previews/flags/FM.png" width="80" alt="Flag of Micronesia"> | — |
| **FR** | France | <img src="docs/previews/flags/FR.png" width="80" alt="Flag of France"> | — |
| **GA** | Gabon | <img src="docs/previews/flags/GA.png" width="80" alt="Flag of Gabon"> | — |
| **GB** | United Kingdom | <img src="docs/previews/flags/GB.png" width="80" alt="Flag of United Kingdom"> | — |
| **GD** | Grenada | <img src="docs/previews/flags/GD.png" width="80" alt="Flag of Grenada"> | — |
| **GE** | Georgia | <img src="docs/previews/flags/GE.png" width="80" alt="Flag of Georgia"> | — |
| **GH** | Ghana | <img src="docs/previews/flags/GH.png" width="80" alt="Flag of Ghana"> | — |
| **GM** | Gambia | <img src="docs/previews/flags/GM.png" width="80" alt="Flag of Gambia"> | — |
| **GN** | Guinea | <img src="docs/previews/flags/GN.png" width="80" alt="Flag of Guinea"> | — |
| **GQ** | Equatorial Guinea | <img src="docs/previews/flags/GQ.png" width="80" alt="Flag of Equatorial Guinea"> | — |
| **GR** | Greece | <img src="docs/previews/flags/GR.png" width="80" alt="Flag of Greece"> | — |
| **GT** | Guatemala | <img src="docs/previews/flags/GT.png" width="80" alt="Flag of Guatemala"> | — |
| **GW** | Guinea-Bissau | <img src="docs/previews/flags/GW.png" width="80" alt="Flag of Guinea-Bissau"> | — |
| **GY** | Guyana | <img src="docs/previews/flags/GY.png" width="80" alt="Flag of Guyana"> | — |
| **HN** | Honduras | <img src="docs/previews/flags/HN.png" width="80" alt="Flag of Honduras"> | — |
| **HR** | Croatia | <img src="docs/previews/flags/HR.png" width="80" alt="Flag of Croatia"> | — |
| **HT** | Haiti | <img src="docs/previews/flags/HT.png" width="80" alt="Flag of Haiti"> | — |
| **HU** | Hungary | <img src="docs/previews/flags/HU.png" width="80" alt="Flag of Hungary"> | — |
| **ID** | Indonesia | <img src="docs/previews/flags/ID.png" width="80" alt="Flag of Indonesia"> | — |
| **IE** | Ireland | <img src="docs/previews/flags/IE.png" width="80" alt="Flag of Ireland"> | — |
| **IL** | Israel | <img src="docs/previews/flags/IL.png" width="80" alt="Flag of Israel"> | — |
| **IN** | India | <img src="docs/previews/flags/IN.png" width="80" alt="Flag of India"> | — |
| **IQ** | Iraq | <img src="docs/previews/flags/IQ.png" width="80" alt="Flag of Iraq"> | — |
| **IR** | Iran | <img src="docs/previews/flags/IR.png" width="80" alt="Flag of Iran"> | — |
| **IS** | Iceland | <img src="docs/previews/flags/IS.png" width="80" alt="Flag of Iceland"> | — |
| **IT** | Italy | <img src="docs/previews/flags/IT.png" width="80" alt="Flag of Italy"> | — |
| **JM** | Jamaica | <img src="docs/previews/flags/JM.png" width="80" alt="Flag of Jamaica"> | — |
| **JO** | Jordan | <img src="docs/previews/flags/JO.png" width="80" alt="Flag of Jordan"> | — |
| **JP** | Japan | <img src="docs/previews/flags/JP.png" width="80" alt="Flag of Japan"> | — |
| **KE** | Kenya | <img src="docs/previews/flags/KE.png" width="80" alt="Flag of Kenya"> | — |
| **KG** | Kyrgyzstan | <img src="docs/previews/flags/KG.png" width="80" alt="Flag of Kyrgyzstan"> | — |
| **KH** | Cambodia | <img src="docs/previews/flags/KH.png" width="80" alt="Flag of Cambodia"> | — |
| **KI** | Kiribati | <img src="docs/previews/flags/KI.png" width="80" alt="Flag of Kiribati"> | — |
| **KM** | Comoros | <img src="docs/previews/flags/KM.png" width="80" alt="Flag of Comoros"> | — |
| **KN** | Saint Kitts and Nevis | <img src="docs/previews/flags/KN.png" width="80" alt="Flag of Saint Kitts and Nevis"> | — |
| **KP** | North Korea | <img src="docs/previews/flags/KP.png" width="80" alt="Flag of North Korea"> | — |
| **KR** | South Korea | <img src="docs/previews/flags/KR.png" width="80" alt="Flag of South Korea"> | — |
| **KW** | Kuwait | <img src="docs/previews/flags/KW.png" width="80" alt="Flag of Kuwait"> | — |
| **KZ** | Kazakhstan | <img src="docs/previews/flags/KZ.png" width="80" alt="Flag of Kazakhstan"> | — |
| **LA** | Laos | <img src="docs/previews/flags/LA.png" width="80" alt="Flag of Laos"> | — |
| **LB** | Lebanon | <img src="docs/previews/flags/LB.png" width="80" alt="Flag of Lebanon"> | — |
| **LC** | Saint Lucia | <img src="docs/previews/flags/LC.png" width="80" alt="Flag of Saint Lucia"> | — |
| **LI** | Liechtenstein | <img src="docs/previews/flags/LI.png" width="80" alt="Flag of Liechtenstein"> | — |
| **LK** | Sri Lanka | <img src="docs/previews/flags/LK.png" width="80" alt="Flag of Sri Lanka"> | — |
| **LR** | Liberia | <img src="docs/previews/flags/LR.png" width="80" alt="Flag of Liberia"> | — |
| **LS** | Lesotho | <img src="docs/previews/flags/LS.png" width="80" alt="Flag of Lesotho"> | — |
| **LT** | Lithuania | <img src="docs/previews/flags/LT.png" width="80" alt="Flag of Lithuania"> | — |
| **LU** | Luxembourg | <img src="docs/previews/flags/LU.png" width="80" alt="Flag of Luxembourg"> | — |
| **LV** | Latvia | <img src="docs/previews/flags/LV.png" width="80" alt="Flag of Latvia"> | — |
| **LY** | Libya | <img src="docs/previews/flags/LY.png" width="80" alt="Flag of Libya"> | — |
| **MA** | Morocco | <img src="docs/previews/flags/MA.png" width="80" alt="Flag of Morocco"> | — |
| **MC** | Monaco | <img src="docs/previews/flags/MC.png" width="80" alt="Flag of Monaco"> | — |
| **MD** | Moldova | <img src="docs/previews/flags/MD.png" width="80" alt="Flag of Moldova"> | — |
| **ME** | Montenegro | <img src="docs/previews/flags/ME.png" width="80" alt="Flag of Montenegro"> | — |
| **MG** | Madagascar | <img src="docs/previews/flags/MG.png" width="80" alt="Flag of Madagascar"> | — |
| **MH** | Marshall Islands | <img src="docs/previews/flags/MH.png" width="80" alt="Flag of Marshall Islands"> | — |
| **MK** | North Macedonia | <img src="docs/previews/flags/MK.png" width="80" alt="Flag of North Macedonia"> | — |
| **ML** | Mali | <img src="docs/previews/flags/ML.png" width="80" alt="Flag of Mali"> | — |
| **MM** | Myanmar | <img src="docs/previews/flags/MM.png" width="80" alt="Flag of Myanmar"> | — |
| **MN** | Mongolia | <img src="docs/previews/flags/MN.png" width="80" alt="Flag of Mongolia"> | — |
| **MR** | Mauritania | <img src="docs/previews/flags/MR.png" width="80" alt="Flag of Mauritania"> | — |
| **MT** | Malta | <img src="docs/previews/flags/MT.png" width="80" alt="Flag of Malta"> | — |
| **MU** | Mauritius | <img src="docs/previews/flags/MU.png" width="80" alt="Flag of Mauritius"> | — |
| **MV** | Maldives | <img src="docs/previews/flags/MV.png" width="80" alt="Flag of Maldives"> | — |
| **MW** | Malawi | <img src="docs/previews/flags/MW.png" width="80" alt="Flag of Malawi"> | — |
| **MX** | Mexico | <img src="docs/previews/flags/MX.png" width="80" alt="Flag of Mexico"> | — |
| **MY** | Malaysia | <img src="docs/previews/flags/MY.png" width="80" alt="Flag of Malaysia"> | — |
| **MZ** | Mozambique | <img src="docs/previews/flags/MZ.png" width="80" alt="Flag of Mozambique"> | — |
| **NA** | Namibia | <img src="docs/previews/flags/NA.png" width="80" alt="Flag of Namibia"> | — |
| **NE** | Niger | <img src="docs/previews/flags/NE.png" width="80" alt="Flag of Niger"> | — |
| **NG** | Nigeria | <img src="docs/previews/flags/NG.png" width="80" alt="Flag of Nigeria"> | — |
| **NI** | Nicaragua | <img src="docs/previews/flags/NI.png" width="80" alt="Flag of Nicaragua"> | — |
| **NL** | Netherlands | <img src="docs/previews/flags/NL.png" width="80" alt="Flag of Netherlands"> | — |
| **NO** | Norway | <img src="docs/previews/flags/NO.png" width="80" alt="Flag of Norway"> | — |
| **NP** | Nepal | <img src="docs/previews/flags/NP.png" width="80" alt="Flag of Nepal"> | — |
| **NR** | Nauru | <img src="docs/previews/flags/NR.png" width="80" alt="Flag of Nauru"> | — |
| **NZ** | New Zealand | <img src="docs/previews/flags/NZ.png" width="80" alt="Flag of New Zealand"> | — |
| **OM** | Oman | <img src="docs/previews/flags/OM.png" width="80" alt="Flag of Oman"> | — |
| **PA** | Panama | <img src="docs/previews/flags/PA.png" width="80" alt="Flag of Panama"> | — |
| **PE** | Peru | <img src="docs/previews/flags/PE.png" width="80" alt="Flag of Peru"> | — |
| **PG** | Papua New Guinea | <img src="docs/previews/flags/PG.png" width="80" alt="Flag of Papua New Guinea"> | — |
| **PH** | Philippines | <img src="docs/previews/flags/PH.png" width="80" alt="Flag of Philippines"> | — |
| **PK** | Pakistan | <img src="docs/previews/flags/PK.png" width="80" alt="Flag of Pakistan"> | — |
| **PL** | Poland | <img src="docs/previews/flags/PL.png" width="80" alt="Flag of Poland"> | — |
| **PS** | Palestine | <img src="docs/previews/flags/PS.png" width="80" alt="Flag of Palestine"> | — |
| **PT** | Portugal | <img src="docs/previews/flags/PT.png" width="80" alt="Flag of Portugal"> | — |
| **PW** | Palau | <img src="docs/previews/flags/PW.png" width="80" alt="Flag of Palau"> | — |
| **PY** | Paraguay | <img src="docs/previews/flags/PY.png" width="80" alt="Flag of Paraguay"> | — |
| **QA** | Qatar | <img src="docs/previews/flags/QA.png" width="80" alt="Flag of Qatar"> | — |
| **RO** | Romania | <img src="docs/previews/flags/RO.png" width="80" alt="Flag of Romania"> | — |
| **RS** | Serbia | <img src="docs/previews/flags/RS.png" width="80" alt="Flag of Serbia"> | — |
| **RU** | Russia | <img src="docs/previews/flags/RU.png" width="80" alt="Flag of Russia"> | — |
| **RW** | Rwanda | <img src="docs/previews/flags/RW.png" width="80" alt="Flag of Rwanda"> | — |
| **SA** | Saudi Arabia | <img src="docs/previews/flags/SA.png" width="80" alt="Flag of Saudi Arabia"> | — |
| **SB** | Solomon Islands | <img src="docs/previews/flags/SB.png" width="80" alt="Flag of Solomon Islands"> | — |
| **SC** | Seychelles | <img src="docs/previews/flags/SC.png" width="80" alt="Flag of Seychelles"> | — |
| **SD** | Sudan | <img src="docs/previews/flags/SD.png" width="80" alt="Flag of Sudan"> | — |
| **SE** | Sweden | <img src="docs/previews/flags/SE.png" width="80" alt="Flag of Sweden"> | — |
| **SG** | Singapore | <img src="docs/previews/flags/SG.png" width="80" alt="Flag of Singapore"> | — |
| **SI** | Slovenia | <img src="docs/previews/flags/SI.png" width="80" alt="Flag of Slovenia"> | — |
| **SK** | Slovakia | <img src="docs/previews/flags/SK.png" width="80" alt="Flag of Slovakia"> | — |
| **SL** | Sierra Leone | <img src="docs/previews/flags/SL.png" width="80" alt="Flag of Sierra Leone"> | — |
| **SM** | San Marino | <img src="docs/previews/flags/SM.png" width="80" alt="Flag of San Marino"> | — |
| **SN** | Senegal | <img src="docs/previews/flags/SN.png" width="80" alt="Flag of Senegal"> | — |
| **SO** | Somalia | <img src="docs/previews/flags/SO.png" width="80" alt="Flag of Somalia"> | — |
| **SR** | Suriname | <img src="docs/previews/flags/SR.png" width="80" alt="Flag of Suriname"> | — |
| **SS** | South Sudan | <img src="docs/previews/flags/SS.png" width="80" alt="Flag of South Sudan"> | — |
| **ST** | Sao Tome and Principe | <img src="docs/previews/flags/ST.png" width="80" alt="Flag of Sao Tome and Principe"> | — |
| **SV** | El Salvador | <img src="docs/previews/flags/SV.png" width="80" alt="Flag of El Salvador"> | — |
| **SY** | Syria | <img src="docs/previews/flags/SY.png" width="80" alt="Flag of Syria"> | — |
| **SZ** | Eswatini | <img src="docs/previews/flags/SZ.png" width="80" alt="Flag of Eswatini"> | — |
| **TD** | Chad | <img src="docs/previews/flags/TD.png" width="80" alt="Flag of Chad"> | — |
| **TG** | Togo | <img src="docs/previews/flags/TG.png" width="80" alt="Flag of Togo"> | — |
| **TH** | Thailand | <img src="docs/previews/flags/TH.png" width="80" alt="Flag of Thailand"> | — |
| **TJ** | Tajikistan | <img src="docs/previews/flags/TJ.png" width="80" alt="Flag of Tajikistan"> | — |
| **TL** | East Timor | <img src="docs/previews/flags/TL.png" width="80" alt="Flag of East Timor"> | — |
| **TM** | Turkmenistan | <img src="docs/previews/flags/TM.png" width="80" alt="Flag of Turkmenistan"> | — |
| **TN** | Tunisia | <img src="docs/previews/flags/TN.png" width="80" alt="Flag of Tunisia"> | — |
| **TO** | Tonga | <img src="docs/previews/flags/TO.png" width="80" alt="Flag of Tonga"> | — |
| **TR** | Turkey | <img src="docs/previews/flags/TR.png" width="80" alt="Flag of Turkey"> | — |
| **TT** | Trinidad and Tobago | <img src="docs/previews/flags/TT.png" width="80" alt="Flag of Trinidad and Tobago"> | — |
| **TV** | Tuvalu | <img src="docs/previews/flags/TV.png" width="80" alt="Flag of Tuvalu"> | — |
| **TZ** | Tanzania | <img src="docs/previews/flags/TZ.png" width="80" alt="Flag of Tanzania"> | — |
| **UA** | Ukraine | <img src="docs/previews/flags/UA.png" width="80" alt="Flag of Ukraine"> | — |
| **UG** | Uganda | <img src="docs/previews/flags/UG.png" width="80" alt="Flag of Uganda"> | — |
| **US** | United States | <img src="docs/previews/flags/US.png" width="80" alt="Flag of United States"> | — |
| **UY** | Uruguay | <img src="docs/previews/flags/UY.png" width="80" alt="Flag of Uruguay"> | — |
| **UZ** | Uzbekistan | <img src="docs/previews/flags/UZ.png" width="80" alt="Flag of Uzbekistan"> | — |
| **VA** | Vatican City | <img src="docs/previews/flags/VA.png" width="80" alt="Flag of Vatican City"> | — |
| **VC** | Saint Vincent and the Grenadines | <img src="docs/previews/flags/VC.png" width="80" alt="Flag of Saint Vincent and the Grenadines"> | — |
| **VE** | Venezuela | <img src="docs/previews/flags/VE.png" width="80" alt="Flag of Venezuela"> | — |
| **VN** | Vietnam | <img src="docs/previews/flags/VN.png" width="80" alt="Flag of Vietnam"> | — |
| **VU** | Vanuatu | <img src="docs/previews/flags/VU.png" width="80" alt="Flag of Vanuatu"> | — |
| **WS** | Samoa | <img src="docs/previews/flags/WS.png" width="80" alt="Flag of Samoa"> | — |
| **YE** | Yemen | <img src="docs/previews/flags/YE.png" width="80" alt="Flag of Yemen"> | — |
| **ZA** | South Africa | <img src="docs/previews/flags/ZA.png" width="80" alt="Flag of South Africa"> | — |
| **ZM** | Zambia | <img src="docs/previews/flags/ZM.png" width="80" alt="Flag of Zambia"> | — |
| **ZW** | Zimbabwe | <img src="docs/previews/flags/ZW.png" width="80" alt="Flag of Zimbabwe"> | — |

<!-- GALLERY:END -->

### US States

<!-- STATE_GALLERY:START -->

All 51 US states (+ DC). Same format as above.

| Code | State | Flag | Outline |
|:----:|:------|:----:|:-------:|
| **AK** | Alaska | <img src="docs/previews/state_flags/AK.png" width="80" alt="Flag of Alaska"> | <img src="docs/previews/state_maps/AK.png" width="96" alt="Outline of Alaska"> |
| **AL** | Alabama | <img src="docs/previews/state_flags/AL.png" width="80" alt="Flag of Alabama"> | <img src="docs/previews/state_maps/AL.png" width="96" alt="Outline of Alabama"> |
| **AR** | Arkansas | <img src="docs/previews/state_flags/AR.png" width="80" alt="Flag of Arkansas"> | <img src="docs/previews/state_maps/AR.png" width="96" alt="Outline of Arkansas"> |
| **AZ** | Arizona | <img src="docs/previews/state_flags/AZ.png" width="80" alt="Flag of Arizona"> | <img src="docs/previews/state_maps/AZ.png" width="96" alt="Outline of Arizona"> |
| **CA** | California | <img src="docs/previews/state_flags/CA.png" width="80" alt="Flag of California"> | <img src="docs/previews/state_maps/CA.png" width="96" alt="Outline of California"> |
| **CO** | Colorado | <img src="docs/previews/state_flags/CO.png" width="80" alt="Flag of Colorado"> | <img src="docs/previews/state_maps/CO.png" width="96" alt="Outline of Colorado"> |
| **CT** | Connecticut | <img src="docs/previews/state_flags/CT.png" width="80" alt="Flag of Connecticut"> | <img src="docs/previews/state_maps/CT.png" width="96" alt="Outline of Connecticut"> |
| **DC** | District of Columbia | <img src="docs/previews/state_flags/DC.png" width="80" alt="Flag of District of Columbia"> | <img src="docs/previews/state_maps/DC.png" width="96" alt="Outline of District of Columbia"> |
| **DE** | Delaware | <img src="docs/previews/state_flags/DE.png" width="80" alt="Flag of Delaware"> | <img src="docs/previews/state_maps/DE.png" width="96" alt="Outline of Delaware"> |
| **FL** | Florida | <img src="docs/previews/state_flags/FL.png" width="80" alt="Flag of Florida"> | <img src="docs/previews/state_maps/FL.png" width="96" alt="Outline of Florida"> |
| **GA** | Georgia | <img src="docs/previews/state_flags/GA.png" width="80" alt="Flag of Georgia"> | <img src="docs/previews/state_maps/GA.png" width="96" alt="Outline of Georgia"> |
| **HI** | Hawaii | <img src="docs/previews/state_flags/HI.png" width="80" alt="Flag of Hawaii"> | <img src="docs/previews/state_maps/HI.png" width="96" alt="Outline of Hawaii"> |
| **IA** | Iowa | <img src="docs/previews/state_flags/IA.png" width="80" alt="Flag of Iowa"> | <img src="docs/previews/state_maps/IA.png" width="96" alt="Outline of Iowa"> |
| **ID** | Idaho | <img src="docs/previews/state_flags/ID.png" width="80" alt="Flag of Idaho"> | <img src="docs/previews/state_maps/ID.png" width="96" alt="Outline of Idaho"> |
| **IL** | Illinois | <img src="docs/previews/state_flags/IL.png" width="80" alt="Flag of Illinois"> | <img src="docs/previews/state_maps/IL.png" width="96" alt="Outline of Illinois"> |
| **IN** | Indiana | <img src="docs/previews/state_flags/IN.png" width="80" alt="Flag of Indiana"> | <img src="docs/previews/state_maps/IN.png" width="96" alt="Outline of Indiana"> |
| **KS** | Kansas | <img src="docs/previews/state_flags/KS.png" width="80" alt="Flag of Kansas"> | <img src="docs/previews/state_maps/KS.png" width="96" alt="Outline of Kansas"> |
| **KY** | Kentucky | <img src="docs/previews/state_flags/KY.png" width="80" alt="Flag of Kentucky"> | <img src="docs/previews/state_maps/KY.png" width="96" alt="Outline of Kentucky"> |
| **LA** | Louisiana | <img src="docs/previews/state_flags/LA.png" width="80" alt="Flag of Louisiana"> | <img src="docs/previews/state_maps/LA.png" width="96" alt="Outline of Louisiana"> |
| **MA** | Massachusetts | <img src="docs/previews/state_flags/MA.png" width="80" alt="Flag of Massachusetts"> | <img src="docs/previews/state_maps/MA.png" width="96" alt="Outline of Massachusetts"> |
| **MD** | Maryland | <img src="docs/previews/state_flags/MD.png" width="80" alt="Flag of Maryland"> | <img src="docs/previews/state_maps/MD.png" width="96" alt="Outline of Maryland"> |
| **ME** | Maine | <img src="docs/previews/state_flags/ME.png" width="80" alt="Flag of Maine"> | <img src="docs/previews/state_maps/ME.png" width="96" alt="Outline of Maine"> |
| **MI** | Michigan | <img src="docs/previews/state_flags/MI.png" width="80" alt="Flag of Michigan"> | <img src="docs/previews/state_maps/MI.png" width="96" alt="Outline of Michigan"> |
| **MN** | Minnesota | <img src="docs/previews/state_flags/MN.png" width="80" alt="Flag of Minnesota"> | <img src="docs/previews/state_maps/MN.png" width="96" alt="Outline of Minnesota"> |
| **MO** | Missouri | <img src="docs/previews/state_flags/MO.png" width="80" alt="Flag of Missouri"> | <img src="docs/previews/state_maps/MO.png" width="96" alt="Outline of Missouri"> |
| **MS** | Mississippi | <img src="docs/previews/state_flags/MS.png" width="80" alt="Flag of Mississippi"> | <img src="docs/previews/state_maps/MS.png" width="96" alt="Outline of Mississippi"> |
| **MT** | Montana | <img src="docs/previews/state_flags/MT.png" width="80" alt="Flag of Montana"> | <img src="docs/previews/state_maps/MT.png" width="96" alt="Outline of Montana"> |
| **NC** | North Carolina | <img src="docs/previews/state_flags/NC.png" width="80" alt="Flag of North Carolina"> | <img src="docs/previews/state_maps/NC.png" width="96" alt="Outline of North Carolina"> |
| **ND** | North Dakota | <img src="docs/previews/state_flags/ND.png" width="80" alt="Flag of North Dakota"> | <img src="docs/previews/state_maps/ND.png" width="96" alt="Outline of North Dakota"> |
| **NE** | Nebraska | <img src="docs/previews/state_flags/NE.png" width="80" alt="Flag of Nebraska"> | <img src="docs/previews/state_maps/NE.png" width="96" alt="Outline of Nebraska"> |
| **NH** | New Hampshire | <img src="docs/previews/state_flags/NH.png" width="80" alt="Flag of New Hampshire"> | <img src="docs/previews/state_maps/NH.png" width="96" alt="Outline of New Hampshire"> |
| **NJ** | New Jersey | <img src="docs/previews/state_flags/NJ.png" width="80" alt="Flag of New Jersey"> | <img src="docs/previews/state_maps/NJ.png" width="96" alt="Outline of New Jersey"> |
| **NM** | New Mexico | <img src="docs/previews/state_flags/NM.png" width="80" alt="Flag of New Mexico"> | <img src="docs/previews/state_maps/NM.png" width="96" alt="Outline of New Mexico"> |
| **NV** | Nevada | <img src="docs/previews/state_flags/NV.png" width="80" alt="Flag of Nevada"> | <img src="docs/previews/state_maps/NV.png" width="96" alt="Outline of Nevada"> |
| **NY** | New York | <img src="docs/previews/state_flags/NY.png" width="80" alt="Flag of New York"> | <img src="docs/previews/state_maps/NY.png" width="96" alt="Outline of New York"> |
| **OH** | Ohio | <img src="docs/previews/state_flags/OH.png" width="80" alt="Flag of Ohio"> | <img src="docs/previews/state_maps/OH.png" width="96" alt="Outline of Ohio"> |
| **OK** | Oklahoma | <img src="docs/previews/state_flags/OK.png" width="80" alt="Flag of Oklahoma"> | <img src="docs/previews/state_maps/OK.png" width="96" alt="Outline of Oklahoma"> |
| **OR** | Oregon | <img src="docs/previews/state_flags/OR.png" width="80" alt="Flag of Oregon"> | <img src="docs/previews/state_maps/OR.png" width="96" alt="Outline of Oregon"> |
| **PA** | Pennsylvania | <img src="docs/previews/state_flags/PA.png" width="80" alt="Flag of Pennsylvania"> | <img src="docs/previews/state_maps/PA.png" width="96" alt="Outline of Pennsylvania"> |
| **RI** | Rhode Island | <img src="docs/previews/state_flags/RI.png" width="80" alt="Flag of Rhode Island"> | <img src="docs/previews/state_maps/RI.png" width="96" alt="Outline of Rhode Island"> |
| **SC** | South Carolina | <img src="docs/previews/state_flags/SC.png" width="80" alt="Flag of South Carolina"> | <img src="docs/previews/state_maps/SC.png" width="96" alt="Outline of South Carolina"> |
| **SD** | South Dakota | <img src="docs/previews/state_flags/SD.png" width="80" alt="Flag of South Dakota"> | <img src="docs/previews/state_maps/SD.png" width="96" alt="Outline of South Dakota"> |
| **TN** | Tennessee | <img src="docs/previews/state_flags/TN.png" width="80" alt="Flag of Tennessee"> | <img src="docs/previews/state_maps/TN.png" width="96" alt="Outline of Tennessee"> |
| **TX** | Texas | <img src="docs/previews/state_flags/TX.png" width="80" alt="Flag of Texas"> | <img src="docs/previews/state_maps/TX.png" width="96" alt="Outline of Texas"> |
| **UT** | Utah | <img src="docs/previews/state_flags/UT.png" width="80" alt="Flag of Utah"> | <img src="docs/previews/state_maps/UT.png" width="96" alt="Outline of Utah"> |
| **VA** | Virginia | <img src="docs/previews/state_flags/VA.png" width="80" alt="Flag of Virginia"> | <img src="docs/previews/state_maps/VA.png" width="96" alt="Outline of Virginia"> |
| **VT** | Vermont | <img src="docs/previews/state_flags/VT.png" width="80" alt="Flag of Vermont"> | <img src="docs/previews/state_maps/VT.png" width="96" alt="Outline of Vermont"> |
| **WA** | Washington | <img src="docs/previews/state_flags/WA.png" width="80" alt="Flag of Washington"> | <img src="docs/previews/state_maps/WA.png" width="96" alt="Outline of Washington"> |
| **WI** | Wisconsin | <img src="docs/previews/state_flags/WI.png" width="80" alt="Flag of Wisconsin"> | <img src="docs/previews/state_maps/WI.png" width="96" alt="Outline of Wisconsin"> |
| **WV** | West Virginia | <img src="docs/previews/state_flags/WV.png" width="80" alt="Flag of West Virginia"> | <img src="docs/previews/state_maps/WV.png" width="96" alt="Outline of West Virginia"> |
| **WY** | Wyoming | <img src="docs/previews/state_flags/WY.png" width="80" alt="Flag of Wyoming"> | <img src="docs/previews/state_maps/WY.png" width="96" alt="Outline of Wyoming"> |

<!-- STATE_GALLERY:END -->

---

## Credits

- Country flags — [lipis/flag-icons](https://github.com/lipis/flag-icons), MIT License.
- Country outlines — [djaiss/mapsicon](https://github.com/djaiss/mapsicon) by **David Jaiss**,
  used with attribution. Not licensed for resale.
- US state flags — [fonttools/region-flags](https://github.com/fonttools/region-flags),
  public domain (Wikipedia).
- US state outlines — [Natural Earth](https://www.naturalearthdata.com/), public domain.
