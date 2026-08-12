# map-n-flag

Country flags and map silhouettes for **195 countries**, baked into flash as
plain C++ arrays for the ESP32. No runtime SVG parsing, no SD card, no external
asset loading — everything is `const` data in `.rodata`.

Built for a 320×240 ESP32 "Cheap Yellow Display" (ILI9341, 4 MB flash, no PSRAM),
but there is nothing board-specific in the library.

- **Zero RAM.** `.bss` and `.data` are both 0 bytes — verified with `xtensa-esp32-elf-size`.
- **No LVGL required.** The core has no dependency beyond `stdint.h`. Draw with
  TFT_eSPI, LovyanGFX, or anything else. LVGL v8/v9 support is an optional header.
- **1.09 MiB** of flash for all 195 flags *and* 191 outlines.

```cpp
#include "map_n_flag.h"

const mnf_img_t *flag = mnf_flag("FR");   // 80x60 indexed image
const mnf_img_t *map  = mnf_map("FR");    // silhouette, same ISO code
const char      *name = mnf_name("FR");   // "France"
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

| | Count | Flash |
|---|---|---|
| Flags @ 80×60 | 195 | 469.2 KiB |
| Outlines @ ≤96 px | 191 | 642.7 KiB |
| **Image data** | **386** | **1,112 KiB (1.09 MiB)** |
| Code (`.text`) | — | 1,102 B |
| **RAM (`.bss` + `.data`)** | — | **0 bytes** |

Four countries have a flag but no outline — mapsicon omits them as too small to
draw: **FM, MH, PS, TV**. Their `map` pointer is `NULL`; use `mnf_has_both()`
to skip them in paired modes.

---

### ⚠️ Commercial use: turn the outlines off

The outline artwork forbids resale, and **not using it is not enough** — the
generated `mnf_table.cpp` references every outline, so the data stays linked
into any firmware that includes this library. To ship something you sell:

```python
# tools/config.py
GENERATE_MAPS = False
```

That emits no outline arrays, NULLs every `map` pointer, and drops the build
from 1.11 MiB to **469 KiB** — leaving only the MIT-licensed flags. `mnf_map()`
then returns `NULL` for every country, so guard with `mnf_has_both()` or check
the pointer.

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

| Scope | Countries | Flags | Maps | Total |
|---|---|---|---|---|
| `all` | 249 | 599.2 KiB | 804.8 KiB | 1.37 MiB |
| `un195` | 195 | 469.2 KiB | 642.7 KiB | **1.09 MiB** ← current |
| `curated` | 62 | 149.2 KiB | 200.6 KiB | 0.34 MiB |

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

| Asset set | Source | License |
|---|---|---|
| Flags | [lipis/flag-icons](https://github.com/lipis/flag-icons) | **MIT** — unrestricted |
| Outlines | [djaiss/mapsicon](https://github.com/djaiss/mapsicon) | ⚠️ **Custom, not OSI** |

mapsicon has no standard license. Its README states, verbatim:

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

---

## Gallery

<!-- GALLERY:START -->

All 195 countries in the current build (`SCOPE = "un195"`). Flags are 80x60; outlines are cropped to their own bounding box and shown centred in a 96x96 square. These PNGs are decoded from the generated C arrays, so they are exactly what the device draws.

| Code | Country | Flag | Outline |
|:----:|:--------|:----:|:-------:|
| **AD** | Andorra | <img src="docs/previews/flags/AD.png" width="80" alt="Flag of Andorra"> | <img src="docs/previews/maps/AD.png" width="96" alt="Outline of Andorra"> |
| **AE** | United Arab Emirates | <img src="docs/previews/flags/AE.png" width="80" alt="Flag of United Arab Emirates"> | <img src="docs/previews/maps/AE.png" width="96" alt="Outline of United Arab Emirates"> |
| **AF** | Afghanistan | <img src="docs/previews/flags/AF.png" width="80" alt="Flag of Afghanistan"> | <img src="docs/previews/maps/AF.png" width="96" alt="Outline of Afghanistan"> |
| **AG** | Antigua and Barbuda | <img src="docs/previews/flags/AG.png" width="80" alt="Flag of Antigua and Barbuda"> | <img src="docs/previews/maps/AG.png" width="96" alt="Outline of Antigua and Barbuda"> |
| **AL** | Albania | <img src="docs/previews/flags/AL.png" width="80" alt="Flag of Albania"> | <img src="docs/previews/maps/AL.png" width="96" alt="Outline of Albania"> |
| **AM** | Armenia | <img src="docs/previews/flags/AM.png" width="80" alt="Flag of Armenia"> | <img src="docs/previews/maps/AM.png" width="96" alt="Outline of Armenia"> |
| **AO** | Angola | <img src="docs/previews/flags/AO.png" width="80" alt="Flag of Angola"> | <img src="docs/previews/maps/AO.png" width="96" alt="Outline of Angola"> |
| **AR** | Argentina | <img src="docs/previews/flags/AR.png" width="80" alt="Flag of Argentina"> | <img src="docs/previews/maps/AR.png" width="96" alt="Outline of Argentina"> |
| **AT** | Austria | <img src="docs/previews/flags/AT.png" width="80" alt="Flag of Austria"> | <img src="docs/previews/maps/AT.png" width="96" alt="Outline of Austria"> |
| **AU** | Australia | <img src="docs/previews/flags/AU.png" width="80" alt="Flag of Australia"> | <img src="docs/previews/maps/AU.png" width="96" alt="Outline of Australia"> |
| **AZ** | Azerbaijan | <img src="docs/previews/flags/AZ.png" width="80" alt="Flag of Azerbaijan"> | <img src="docs/previews/maps/AZ.png" width="96" alt="Outline of Azerbaijan"> |
| **BA** | Bosnia and Herzegovina | <img src="docs/previews/flags/BA.png" width="80" alt="Flag of Bosnia and Herzegovina"> | <img src="docs/previews/maps/BA.png" width="96" alt="Outline of Bosnia and Herzegovina"> |
| **BB** | Barbados | <img src="docs/previews/flags/BB.png" width="80" alt="Flag of Barbados"> | <img src="docs/previews/maps/BB.png" width="96" alt="Outline of Barbados"> |
| **BD** | Bangladesh | <img src="docs/previews/flags/BD.png" width="80" alt="Flag of Bangladesh"> | <img src="docs/previews/maps/BD.png" width="96" alt="Outline of Bangladesh"> |
| **BE** | Belgium | <img src="docs/previews/flags/BE.png" width="80" alt="Flag of Belgium"> | <img src="docs/previews/maps/BE.png" width="96" alt="Outline of Belgium"> |
| **BF** | Burkina Faso | <img src="docs/previews/flags/BF.png" width="80" alt="Flag of Burkina Faso"> | <img src="docs/previews/maps/BF.png" width="96" alt="Outline of Burkina Faso"> |
| **BG** | Bulgaria | <img src="docs/previews/flags/BG.png" width="80" alt="Flag of Bulgaria"> | <img src="docs/previews/maps/BG.png" width="96" alt="Outline of Bulgaria"> |
| **BH** | Bahrain | <img src="docs/previews/flags/BH.png" width="80" alt="Flag of Bahrain"> | <img src="docs/previews/maps/BH.png" width="96" alt="Outline of Bahrain"> |
| **BI** | Burundi | <img src="docs/previews/flags/BI.png" width="80" alt="Flag of Burundi"> | <img src="docs/previews/maps/BI.png" width="96" alt="Outline of Burundi"> |
| **BJ** | Benin | <img src="docs/previews/flags/BJ.png" width="80" alt="Flag of Benin"> | <img src="docs/previews/maps/BJ.png" width="96" alt="Outline of Benin"> |
| **BN** | Brunei | <img src="docs/previews/flags/BN.png" width="80" alt="Flag of Brunei"> | <img src="docs/previews/maps/BN.png" width="96" alt="Outline of Brunei"> |
| **BO** | Bolivia | <img src="docs/previews/flags/BO.png" width="80" alt="Flag of Bolivia"> | <img src="docs/previews/maps/BO.png" width="96" alt="Outline of Bolivia"> |
| **BR** | Brazil | <img src="docs/previews/flags/BR.png" width="80" alt="Flag of Brazil"> | <img src="docs/previews/maps/BR.png" width="96" alt="Outline of Brazil"> |
| **BS** | Bahamas | <img src="docs/previews/flags/BS.png" width="80" alt="Flag of Bahamas"> | <img src="docs/previews/maps/BS.png" width="96" alt="Outline of Bahamas"> |
| **BT** | Bhutan | <img src="docs/previews/flags/BT.png" width="80" alt="Flag of Bhutan"> | <img src="docs/previews/maps/BT.png" width="96" alt="Outline of Bhutan"> |
| **BW** | Botswana | <img src="docs/previews/flags/BW.png" width="80" alt="Flag of Botswana"> | <img src="docs/previews/maps/BW.png" width="96" alt="Outline of Botswana"> |
| **BY** | Belarus | <img src="docs/previews/flags/BY.png" width="80" alt="Flag of Belarus"> | <img src="docs/previews/maps/BY.png" width="96" alt="Outline of Belarus"> |
| **BZ** | Belize | <img src="docs/previews/flags/BZ.png" width="80" alt="Flag of Belize"> | <img src="docs/previews/maps/BZ.png" width="96" alt="Outline of Belize"> |
| **CA** | Canada | <img src="docs/previews/flags/CA.png" width="80" alt="Flag of Canada"> | <img src="docs/previews/maps/CA.png" width="96" alt="Outline of Canada"> |
| **CD** | DR Congo | <img src="docs/previews/flags/CD.png" width="80" alt="Flag of DR Congo"> | <img src="docs/previews/maps/CD.png" width="96" alt="Outline of DR Congo"> |
| **CF** | Central African Republic | <img src="docs/previews/flags/CF.png" width="80" alt="Flag of Central African Republic"> | <img src="docs/previews/maps/CF.png" width="96" alt="Outline of Central African Republic"> |
| **CG** | Congo | <img src="docs/previews/flags/CG.png" width="80" alt="Flag of Congo"> | <img src="docs/previews/maps/CG.png" width="96" alt="Outline of Congo"> |
| **CH** | Switzerland | <img src="docs/previews/flags/CH.png" width="80" alt="Flag of Switzerland"> | <img src="docs/previews/maps/CH.png" width="96" alt="Outline of Switzerland"> |
| **CI** | Ivory Coast | <img src="docs/previews/flags/CI.png" width="80" alt="Flag of Ivory Coast"> | <img src="docs/previews/maps/CI.png" width="96" alt="Outline of Ivory Coast"> |
| **CL** | Chile | <img src="docs/previews/flags/CL.png" width="80" alt="Flag of Chile"> | <img src="docs/previews/maps/CL.png" width="96" alt="Outline of Chile"> |
| **CM** | Cameroon | <img src="docs/previews/flags/CM.png" width="80" alt="Flag of Cameroon"> | <img src="docs/previews/maps/CM.png" width="96" alt="Outline of Cameroon"> |
| **CN** | China | <img src="docs/previews/flags/CN.png" width="80" alt="Flag of China"> | <img src="docs/previews/maps/CN.png" width="96" alt="Outline of China"> |
| **CO** | Colombia | <img src="docs/previews/flags/CO.png" width="80" alt="Flag of Colombia"> | <img src="docs/previews/maps/CO.png" width="96" alt="Outline of Colombia"> |
| **CR** | Costa Rica | <img src="docs/previews/flags/CR.png" width="80" alt="Flag of Costa Rica"> | <img src="docs/previews/maps/CR.png" width="96" alt="Outline of Costa Rica"> |
| **CU** | Cuba | <img src="docs/previews/flags/CU.png" width="80" alt="Flag of Cuba"> | <img src="docs/previews/maps/CU.png" width="96" alt="Outline of Cuba"> |
| **CV** | Cape Verde | <img src="docs/previews/flags/CV.png" width="80" alt="Flag of Cape Verde"> | <img src="docs/previews/maps/CV.png" width="96" alt="Outline of Cape Verde"> |
| **CY** | Cyprus | <img src="docs/previews/flags/CY.png" width="80" alt="Flag of Cyprus"> | <img src="docs/previews/maps/CY.png" width="96" alt="Outline of Cyprus"> |
| **CZ** | Czechia | <img src="docs/previews/flags/CZ.png" width="80" alt="Flag of Czechia"> | <img src="docs/previews/maps/CZ.png" width="96" alt="Outline of Czechia"> |
| **DE** | Germany | <img src="docs/previews/flags/DE.png" width="80" alt="Flag of Germany"> | <img src="docs/previews/maps/DE.png" width="96" alt="Outline of Germany"> |
| **DJ** | Djibouti | <img src="docs/previews/flags/DJ.png" width="80" alt="Flag of Djibouti"> | <img src="docs/previews/maps/DJ.png" width="96" alt="Outline of Djibouti"> |
| **DK** | Denmark | <img src="docs/previews/flags/DK.png" width="80" alt="Flag of Denmark"> | <img src="docs/previews/maps/DK.png" width="96" alt="Outline of Denmark"> |
| **DM** | Dominica | <img src="docs/previews/flags/DM.png" width="80" alt="Flag of Dominica"> | <img src="docs/previews/maps/DM.png" width="96" alt="Outline of Dominica"> |
| **DO** | Dominican Republic | <img src="docs/previews/flags/DO.png" width="80" alt="Flag of Dominican Republic"> | <img src="docs/previews/maps/DO.png" width="96" alt="Outline of Dominican Republic"> |
| **DZ** | Algeria | <img src="docs/previews/flags/DZ.png" width="80" alt="Flag of Algeria"> | <img src="docs/previews/maps/DZ.png" width="96" alt="Outline of Algeria"> |
| **EC** | Ecuador | <img src="docs/previews/flags/EC.png" width="80" alt="Flag of Ecuador"> | <img src="docs/previews/maps/EC.png" width="96" alt="Outline of Ecuador"> |
| **EE** | Estonia | <img src="docs/previews/flags/EE.png" width="80" alt="Flag of Estonia"> | <img src="docs/previews/maps/EE.png" width="96" alt="Outline of Estonia"> |
| **EG** | Egypt | <img src="docs/previews/flags/EG.png" width="80" alt="Flag of Egypt"> | <img src="docs/previews/maps/EG.png" width="96" alt="Outline of Egypt"> |
| **ER** | Eritrea | <img src="docs/previews/flags/ER.png" width="80" alt="Flag of Eritrea"> | <img src="docs/previews/maps/ER.png" width="96" alt="Outline of Eritrea"> |
| **ES** | Spain | <img src="docs/previews/flags/ES.png" width="80" alt="Flag of Spain"> | <img src="docs/previews/maps/ES.png" width="96" alt="Outline of Spain"> |
| **ET** | Ethiopia | <img src="docs/previews/flags/ET.png" width="80" alt="Flag of Ethiopia"> | <img src="docs/previews/maps/ET.png" width="96" alt="Outline of Ethiopia"> |
| **FI** | Finland | <img src="docs/previews/flags/FI.png" width="80" alt="Flag of Finland"> | <img src="docs/previews/maps/FI.png" width="96" alt="Outline of Finland"> |
| **FJ** | Fiji | <img src="docs/previews/flags/FJ.png" width="80" alt="Flag of Fiji"> | <img src="docs/previews/maps/FJ.png" width="96" alt="Outline of Fiji"> |
| **FM** | Micronesia | <img src="docs/previews/flags/FM.png" width="80" alt="Flag of Micronesia"> | — |
| **FR** | France | <img src="docs/previews/flags/FR.png" width="80" alt="Flag of France"> | <img src="docs/previews/maps/FR.png" width="96" alt="Outline of France"> |
| **GA** | Gabon | <img src="docs/previews/flags/GA.png" width="80" alt="Flag of Gabon"> | <img src="docs/previews/maps/GA.png" width="96" alt="Outline of Gabon"> |
| **GB** | United Kingdom | <img src="docs/previews/flags/GB.png" width="80" alt="Flag of United Kingdom"> | <img src="docs/previews/maps/GB.png" width="96" alt="Outline of United Kingdom"> |
| **GD** | Grenada | <img src="docs/previews/flags/GD.png" width="80" alt="Flag of Grenada"> | <img src="docs/previews/maps/GD.png" width="96" alt="Outline of Grenada"> |
| **GE** | Georgia | <img src="docs/previews/flags/GE.png" width="80" alt="Flag of Georgia"> | <img src="docs/previews/maps/GE.png" width="96" alt="Outline of Georgia"> |
| **GH** | Ghana | <img src="docs/previews/flags/GH.png" width="80" alt="Flag of Ghana"> | <img src="docs/previews/maps/GH.png" width="96" alt="Outline of Ghana"> |
| **GM** | Gambia | <img src="docs/previews/flags/GM.png" width="80" alt="Flag of Gambia"> | <img src="docs/previews/maps/GM.png" width="96" alt="Outline of Gambia"> |
| **GN** | Guinea | <img src="docs/previews/flags/GN.png" width="80" alt="Flag of Guinea"> | <img src="docs/previews/maps/GN.png" width="96" alt="Outline of Guinea"> |
| **GQ** | Equatorial Guinea | <img src="docs/previews/flags/GQ.png" width="80" alt="Flag of Equatorial Guinea"> | <img src="docs/previews/maps/GQ.png" width="96" alt="Outline of Equatorial Guinea"> |
| **GR** | Greece | <img src="docs/previews/flags/GR.png" width="80" alt="Flag of Greece"> | <img src="docs/previews/maps/GR.png" width="96" alt="Outline of Greece"> |
| **GT** | Guatemala | <img src="docs/previews/flags/GT.png" width="80" alt="Flag of Guatemala"> | <img src="docs/previews/maps/GT.png" width="96" alt="Outline of Guatemala"> |
| **GW** | Guinea-Bissau | <img src="docs/previews/flags/GW.png" width="80" alt="Flag of Guinea-Bissau"> | <img src="docs/previews/maps/GW.png" width="96" alt="Outline of Guinea-Bissau"> |
| **GY** | Guyana | <img src="docs/previews/flags/GY.png" width="80" alt="Flag of Guyana"> | <img src="docs/previews/maps/GY.png" width="96" alt="Outline of Guyana"> |
| **HN** | Honduras | <img src="docs/previews/flags/HN.png" width="80" alt="Flag of Honduras"> | <img src="docs/previews/maps/HN.png" width="96" alt="Outline of Honduras"> |
| **HR** | Croatia | <img src="docs/previews/flags/HR.png" width="80" alt="Flag of Croatia"> | <img src="docs/previews/maps/HR.png" width="96" alt="Outline of Croatia"> |
| **HT** | Haiti | <img src="docs/previews/flags/HT.png" width="80" alt="Flag of Haiti"> | <img src="docs/previews/maps/HT.png" width="96" alt="Outline of Haiti"> |
| **HU** | Hungary | <img src="docs/previews/flags/HU.png" width="80" alt="Flag of Hungary"> | <img src="docs/previews/maps/HU.png" width="96" alt="Outline of Hungary"> |
| **ID** | Indonesia | <img src="docs/previews/flags/ID.png" width="80" alt="Flag of Indonesia"> | <img src="docs/previews/maps/ID.png" width="96" alt="Outline of Indonesia"> |
| **IE** | Ireland | <img src="docs/previews/flags/IE.png" width="80" alt="Flag of Ireland"> | <img src="docs/previews/maps/IE.png" width="96" alt="Outline of Ireland"> |
| **IL** | Israel | <img src="docs/previews/flags/IL.png" width="80" alt="Flag of Israel"> | <img src="docs/previews/maps/IL.png" width="96" alt="Outline of Israel"> |
| **IN** | India | <img src="docs/previews/flags/IN.png" width="80" alt="Flag of India"> | <img src="docs/previews/maps/IN.png" width="96" alt="Outline of India"> |
| **IQ** | Iraq | <img src="docs/previews/flags/IQ.png" width="80" alt="Flag of Iraq"> | <img src="docs/previews/maps/IQ.png" width="96" alt="Outline of Iraq"> |
| **IR** | Iran | <img src="docs/previews/flags/IR.png" width="80" alt="Flag of Iran"> | <img src="docs/previews/maps/IR.png" width="96" alt="Outline of Iran"> |
| **IS** | Iceland | <img src="docs/previews/flags/IS.png" width="80" alt="Flag of Iceland"> | <img src="docs/previews/maps/IS.png" width="96" alt="Outline of Iceland"> |
| **IT** | Italy | <img src="docs/previews/flags/IT.png" width="80" alt="Flag of Italy"> | <img src="docs/previews/maps/IT.png" width="96" alt="Outline of Italy"> |
| **JM** | Jamaica | <img src="docs/previews/flags/JM.png" width="80" alt="Flag of Jamaica"> | <img src="docs/previews/maps/JM.png" width="96" alt="Outline of Jamaica"> |
| **JO** | Jordan | <img src="docs/previews/flags/JO.png" width="80" alt="Flag of Jordan"> | <img src="docs/previews/maps/JO.png" width="96" alt="Outline of Jordan"> |
| **JP** | Japan | <img src="docs/previews/flags/JP.png" width="80" alt="Flag of Japan"> | <img src="docs/previews/maps/JP.png" width="96" alt="Outline of Japan"> |
| **KE** | Kenya | <img src="docs/previews/flags/KE.png" width="80" alt="Flag of Kenya"> | <img src="docs/previews/maps/KE.png" width="96" alt="Outline of Kenya"> |
| **KG** | Kyrgyzstan | <img src="docs/previews/flags/KG.png" width="80" alt="Flag of Kyrgyzstan"> | <img src="docs/previews/maps/KG.png" width="96" alt="Outline of Kyrgyzstan"> |
| **KH** | Cambodia | <img src="docs/previews/flags/KH.png" width="80" alt="Flag of Cambodia"> | <img src="docs/previews/maps/KH.png" width="96" alt="Outline of Cambodia"> |
| **KI** | Kiribati | <img src="docs/previews/flags/KI.png" width="80" alt="Flag of Kiribati"> | <img src="docs/previews/maps/KI.png" width="96" alt="Outline of Kiribati"> |
| **KM** | Comoros | <img src="docs/previews/flags/KM.png" width="80" alt="Flag of Comoros"> | <img src="docs/previews/maps/KM.png" width="96" alt="Outline of Comoros"> |
| **KN** | Saint Kitts and Nevis | <img src="docs/previews/flags/KN.png" width="80" alt="Flag of Saint Kitts and Nevis"> | <img src="docs/previews/maps/KN.png" width="96" alt="Outline of Saint Kitts and Nevis"> |
| **KP** | North Korea | <img src="docs/previews/flags/KP.png" width="80" alt="Flag of North Korea"> | <img src="docs/previews/maps/KP.png" width="96" alt="Outline of North Korea"> |
| **KR** | South Korea | <img src="docs/previews/flags/KR.png" width="80" alt="Flag of South Korea"> | <img src="docs/previews/maps/KR.png" width="96" alt="Outline of South Korea"> |
| **KW** | Kuwait | <img src="docs/previews/flags/KW.png" width="80" alt="Flag of Kuwait"> | <img src="docs/previews/maps/KW.png" width="96" alt="Outline of Kuwait"> |
| **KZ** | Kazakhstan | <img src="docs/previews/flags/KZ.png" width="80" alt="Flag of Kazakhstan"> | <img src="docs/previews/maps/KZ.png" width="96" alt="Outline of Kazakhstan"> |
| **LA** | Laos | <img src="docs/previews/flags/LA.png" width="80" alt="Flag of Laos"> | <img src="docs/previews/maps/LA.png" width="96" alt="Outline of Laos"> |
| **LB** | Lebanon | <img src="docs/previews/flags/LB.png" width="80" alt="Flag of Lebanon"> | <img src="docs/previews/maps/LB.png" width="96" alt="Outline of Lebanon"> |
| **LC** | Saint Lucia | <img src="docs/previews/flags/LC.png" width="80" alt="Flag of Saint Lucia"> | <img src="docs/previews/maps/LC.png" width="96" alt="Outline of Saint Lucia"> |
| **LI** | Liechtenstein | <img src="docs/previews/flags/LI.png" width="80" alt="Flag of Liechtenstein"> | <img src="docs/previews/maps/LI.png" width="96" alt="Outline of Liechtenstein"> |
| **LK** | Sri Lanka | <img src="docs/previews/flags/LK.png" width="80" alt="Flag of Sri Lanka"> | <img src="docs/previews/maps/LK.png" width="96" alt="Outline of Sri Lanka"> |
| **LR** | Liberia | <img src="docs/previews/flags/LR.png" width="80" alt="Flag of Liberia"> | <img src="docs/previews/maps/LR.png" width="96" alt="Outline of Liberia"> |
| **LS** | Lesotho | <img src="docs/previews/flags/LS.png" width="80" alt="Flag of Lesotho"> | <img src="docs/previews/maps/LS.png" width="96" alt="Outline of Lesotho"> |
| **LT** | Lithuania | <img src="docs/previews/flags/LT.png" width="80" alt="Flag of Lithuania"> | <img src="docs/previews/maps/LT.png" width="96" alt="Outline of Lithuania"> |
| **LU** | Luxembourg | <img src="docs/previews/flags/LU.png" width="80" alt="Flag of Luxembourg"> | <img src="docs/previews/maps/LU.png" width="96" alt="Outline of Luxembourg"> |
| **LV** | Latvia | <img src="docs/previews/flags/LV.png" width="80" alt="Flag of Latvia"> | <img src="docs/previews/maps/LV.png" width="96" alt="Outline of Latvia"> |
| **LY** | Libya | <img src="docs/previews/flags/LY.png" width="80" alt="Flag of Libya"> | <img src="docs/previews/maps/LY.png" width="96" alt="Outline of Libya"> |
| **MA** | Morocco | <img src="docs/previews/flags/MA.png" width="80" alt="Flag of Morocco"> | <img src="docs/previews/maps/MA.png" width="96" alt="Outline of Morocco"> |
| **MC** | Monaco | <img src="docs/previews/flags/MC.png" width="80" alt="Flag of Monaco"> | <img src="docs/previews/maps/MC.png" width="96" alt="Outline of Monaco"> |
| **MD** | Moldova | <img src="docs/previews/flags/MD.png" width="80" alt="Flag of Moldova"> | <img src="docs/previews/maps/MD.png" width="96" alt="Outline of Moldova"> |
| **ME** | Montenegro | <img src="docs/previews/flags/ME.png" width="80" alt="Flag of Montenegro"> | <img src="docs/previews/maps/ME.png" width="96" alt="Outline of Montenegro"> |
| **MG** | Madagascar | <img src="docs/previews/flags/MG.png" width="80" alt="Flag of Madagascar"> | <img src="docs/previews/maps/MG.png" width="96" alt="Outline of Madagascar"> |
| **MH** | Marshall Islands | <img src="docs/previews/flags/MH.png" width="80" alt="Flag of Marshall Islands"> | — |
| **MK** | North Macedonia | <img src="docs/previews/flags/MK.png" width="80" alt="Flag of North Macedonia"> | <img src="docs/previews/maps/MK.png" width="96" alt="Outline of North Macedonia"> |
| **ML** | Mali | <img src="docs/previews/flags/ML.png" width="80" alt="Flag of Mali"> | <img src="docs/previews/maps/ML.png" width="96" alt="Outline of Mali"> |
| **MM** | Myanmar | <img src="docs/previews/flags/MM.png" width="80" alt="Flag of Myanmar"> | <img src="docs/previews/maps/MM.png" width="96" alt="Outline of Myanmar"> |
| **MN** | Mongolia | <img src="docs/previews/flags/MN.png" width="80" alt="Flag of Mongolia"> | <img src="docs/previews/maps/MN.png" width="96" alt="Outline of Mongolia"> |
| **MR** | Mauritania | <img src="docs/previews/flags/MR.png" width="80" alt="Flag of Mauritania"> | <img src="docs/previews/maps/MR.png" width="96" alt="Outline of Mauritania"> |
| **MT** | Malta | <img src="docs/previews/flags/MT.png" width="80" alt="Flag of Malta"> | <img src="docs/previews/maps/MT.png" width="96" alt="Outline of Malta"> |
| **MU** | Mauritius | <img src="docs/previews/flags/MU.png" width="80" alt="Flag of Mauritius"> | <img src="docs/previews/maps/MU.png" width="96" alt="Outline of Mauritius"> |
| **MV** | Maldives | <img src="docs/previews/flags/MV.png" width="80" alt="Flag of Maldives"> | <img src="docs/previews/maps/MV.png" width="96" alt="Outline of Maldives"> |
| **MW** | Malawi | <img src="docs/previews/flags/MW.png" width="80" alt="Flag of Malawi"> | <img src="docs/previews/maps/MW.png" width="96" alt="Outline of Malawi"> |
| **MX** | Mexico | <img src="docs/previews/flags/MX.png" width="80" alt="Flag of Mexico"> | <img src="docs/previews/maps/MX.png" width="96" alt="Outline of Mexico"> |
| **MY** | Malaysia | <img src="docs/previews/flags/MY.png" width="80" alt="Flag of Malaysia"> | <img src="docs/previews/maps/MY.png" width="96" alt="Outline of Malaysia"> |
| **MZ** | Mozambique | <img src="docs/previews/flags/MZ.png" width="80" alt="Flag of Mozambique"> | <img src="docs/previews/maps/MZ.png" width="96" alt="Outline of Mozambique"> |
| **NA** | Namibia | <img src="docs/previews/flags/NA.png" width="80" alt="Flag of Namibia"> | <img src="docs/previews/maps/NA.png" width="96" alt="Outline of Namibia"> |
| **NE** | Niger | <img src="docs/previews/flags/NE.png" width="80" alt="Flag of Niger"> | <img src="docs/previews/maps/NE.png" width="96" alt="Outline of Niger"> |
| **NG** | Nigeria | <img src="docs/previews/flags/NG.png" width="80" alt="Flag of Nigeria"> | <img src="docs/previews/maps/NG.png" width="96" alt="Outline of Nigeria"> |
| **NI** | Nicaragua | <img src="docs/previews/flags/NI.png" width="80" alt="Flag of Nicaragua"> | <img src="docs/previews/maps/NI.png" width="96" alt="Outline of Nicaragua"> |
| **NL** | Netherlands | <img src="docs/previews/flags/NL.png" width="80" alt="Flag of Netherlands"> | <img src="docs/previews/maps/NL.png" width="96" alt="Outline of Netherlands"> |
| **NO** | Norway | <img src="docs/previews/flags/NO.png" width="80" alt="Flag of Norway"> | <img src="docs/previews/maps/NO.png" width="96" alt="Outline of Norway"> |
| **NP** | Nepal | <img src="docs/previews/flags/NP.png" width="80" alt="Flag of Nepal"> | <img src="docs/previews/maps/NP.png" width="96" alt="Outline of Nepal"> |
| **NR** | Nauru | <img src="docs/previews/flags/NR.png" width="80" alt="Flag of Nauru"> | <img src="docs/previews/maps/NR.png" width="96" alt="Outline of Nauru"> |
| **NZ** | New Zealand | <img src="docs/previews/flags/NZ.png" width="80" alt="Flag of New Zealand"> | <img src="docs/previews/maps/NZ.png" width="96" alt="Outline of New Zealand"> |
| **OM** | Oman | <img src="docs/previews/flags/OM.png" width="80" alt="Flag of Oman"> | <img src="docs/previews/maps/OM.png" width="96" alt="Outline of Oman"> |
| **PA** | Panama | <img src="docs/previews/flags/PA.png" width="80" alt="Flag of Panama"> | <img src="docs/previews/maps/PA.png" width="96" alt="Outline of Panama"> |
| **PE** | Peru | <img src="docs/previews/flags/PE.png" width="80" alt="Flag of Peru"> | <img src="docs/previews/maps/PE.png" width="96" alt="Outline of Peru"> |
| **PG** | Papua New Guinea | <img src="docs/previews/flags/PG.png" width="80" alt="Flag of Papua New Guinea"> | <img src="docs/previews/maps/PG.png" width="96" alt="Outline of Papua New Guinea"> |
| **PH** | Philippines | <img src="docs/previews/flags/PH.png" width="80" alt="Flag of Philippines"> | <img src="docs/previews/maps/PH.png" width="96" alt="Outline of Philippines"> |
| **PK** | Pakistan | <img src="docs/previews/flags/PK.png" width="80" alt="Flag of Pakistan"> | <img src="docs/previews/maps/PK.png" width="96" alt="Outline of Pakistan"> |
| **PL** | Poland | <img src="docs/previews/flags/PL.png" width="80" alt="Flag of Poland"> | <img src="docs/previews/maps/PL.png" width="96" alt="Outline of Poland"> |
| **PS** | Palestine | <img src="docs/previews/flags/PS.png" width="80" alt="Flag of Palestine"> | — |
| **PT** | Portugal | <img src="docs/previews/flags/PT.png" width="80" alt="Flag of Portugal"> | <img src="docs/previews/maps/PT.png" width="96" alt="Outline of Portugal"> |
| **PW** | Palau | <img src="docs/previews/flags/PW.png" width="80" alt="Flag of Palau"> | <img src="docs/previews/maps/PW.png" width="96" alt="Outline of Palau"> |
| **PY** | Paraguay | <img src="docs/previews/flags/PY.png" width="80" alt="Flag of Paraguay"> | <img src="docs/previews/maps/PY.png" width="96" alt="Outline of Paraguay"> |
| **QA** | Qatar | <img src="docs/previews/flags/QA.png" width="80" alt="Flag of Qatar"> | <img src="docs/previews/maps/QA.png" width="96" alt="Outline of Qatar"> |
| **RO** | Romania | <img src="docs/previews/flags/RO.png" width="80" alt="Flag of Romania"> | <img src="docs/previews/maps/RO.png" width="96" alt="Outline of Romania"> |
| **RS** | Serbia | <img src="docs/previews/flags/RS.png" width="80" alt="Flag of Serbia"> | <img src="docs/previews/maps/RS.png" width="96" alt="Outline of Serbia"> |
| **RU** | Russia | <img src="docs/previews/flags/RU.png" width="80" alt="Flag of Russia"> | <img src="docs/previews/maps/RU.png" width="96" alt="Outline of Russia"> |
| **RW** | Rwanda | <img src="docs/previews/flags/RW.png" width="80" alt="Flag of Rwanda"> | <img src="docs/previews/maps/RW.png" width="96" alt="Outline of Rwanda"> |
| **SA** | Saudi Arabia | <img src="docs/previews/flags/SA.png" width="80" alt="Flag of Saudi Arabia"> | <img src="docs/previews/maps/SA.png" width="96" alt="Outline of Saudi Arabia"> |
| **SB** | Solomon Islands | <img src="docs/previews/flags/SB.png" width="80" alt="Flag of Solomon Islands"> | <img src="docs/previews/maps/SB.png" width="96" alt="Outline of Solomon Islands"> |
| **SC** | Seychelles | <img src="docs/previews/flags/SC.png" width="80" alt="Flag of Seychelles"> | <img src="docs/previews/maps/SC.png" width="96" alt="Outline of Seychelles"> |
| **SD** | Sudan | <img src="docs/previews/flags/SD.png" width="80" alt="Flag of Sudan"> | <img src="docs/previews/maps/SD.png" width="96" alt="Outline of Sudan"> |
| **SE** | Sweden | <img src="docs/previews/flags/SE.png" width="80" alt="Flag of Sweden"> | <img src="docs/previews/maps/SE.png" width="96" alt="Outline of Sweden"> |
| **SG** | Singapore | <img src="docs/previews/flags/SG.png" width="80" alt="Flag of Singapore"> | <img src="docs/previews/maps/SG.png" width="96" alt="Outline of Singapore"> |
| **SI** | Slovenia | <img src="docs/previews/flags/SI.png" width="80" alt="Flag of Slovenia"> | <img src="docs/previews/maps/SI.png" width="96" alt="Outline of Slovenia"> |
| **SK** | Slovakia | <img src="docs/previews/flags/SK.png" width="80" alt="Flag of Slovakia"> | <img src="docs/previews/maps/SK.png" width="96" alt="Outline of Slovakia"> |
| **SL** | Sierra Leone | <img src="docs/previews/flags/SL.png" width="80" alt="Flag of Sierra Leone"> | <img src="docs/previews/maps/SL.png" width="96" alt="Outline of Sierra Leone"> |
| **SM** | San Marino | <img src="docs/previews/flags/SM.png" width="80" alt="Flag of San Marino"> | <img src="docs/previews/maps/SM.png" width="96" alt="Outline of San Marino"> |
| **SN** | Senegal | <img src="docs/previews/flags/SN.png" width="80" alt="Flag of Senegal"> | <img src="docs/previews/maps/SN.png" width="96" alt="Outline of Senegal"> |
| **SO** | Somalia | <img src="docs/previews/flags/SO.png" width="80" alt="Flag of Somalia"> | <img src="docs/previews/maps/SO.png" width="96" alt="Outline of Somalia"> |
| **SR** | Suriname | <img src="docs/previews/flags/SR.png" width="80" alt="Flag of Suriname"> | <img src="docs/previews/maps/SR.png" width="96" alt="Outline of Suriname"> |
| **SS** | South Sudan | <img src="docs/previews/flags/SS.png" width="80" alt="Flag of South Sudan"> | <img src="docs/previews/maps/SS.png" width="96" alt="Outline of South Sudan"> |
| **ST** | Sao Tome and Principe | <img src="docs/previews/flags/ST.png" width="80" alt="Flag of Sao Tome and Principe"> | <img src="docs/previews/maps/ST.png" width="96" alt="Outline of Sao Tome and Principe"> |
| **SV** | El Salvador | <img src="docs/previews/flags/SV.png" width="80" alt="Flag of El Salvador"> | <img src="docs/previews/maps/SV.png" width="96" alt="Outline of El Salvador"> |
| **SY** | Syria | <img src="docs/previews/flags/SY.png" width="80" alt="Flag of Syria"> | <img src="docs/previews/maps/SY.png" width="96" alt="Outline of Syria"> |
| **SZ** | Eswatini | <img src="docs/previews/flags/SZ.png" width="80" alt="Flag of Eswatini"> | <img src="docs/previews/maps/SZ.png" width="96" alt="Outline of Eswatini"> |
| **TD** | Chad | <img src="docs/previews/flags/TD.png" width="80" alt="Flag of Chad"> | <img src="docs/previews/maps/TD.png" width="96" alt="Outline of Chad"> |
| **TG** | Togo | <img src="docs/previews/flags/TG.png" width="80" alt="Flag of Togo"> | <img src="docs/previews/maps/TG.png" width="96" alt="Outline of Togo"> |
| **TH** | Thailand | <img src="docs/previews/flags/TH.png" width="80" alt="Flag of Thailand"> | <img src="docs/previews/maps/TH.png" width="96" alt="Outline of Thailand"> |
| **TJ** | Tajikistan | <img src="docs/previews/flags/TJ.png" width="80" alt="Flag of Tajikistan"> | <img src="docs/previews/maps/TJ.png" width="96" alt="Outline of Tajikistan"> |
| **TL** | East Timor | <img src="docs/previews/flags/TL.png" width="80" alt="Flag of East Timor"> | <img src="docs/previews/maps/TL.png" width="96" alt="Outline of East Timor"> |
| **TM** | Turkmenistan | <img src="docs/previews/flags/TM.png" width="80" alt="Flag of Turkmenistan"> | <img src="docs/previews/maps/TM.png" width="96" alt="Outline of Turkmenistan"> |
| **TN** | Tunisia | <img src="docs/previews/flags/TN.png" width="80" alt="Flag of Tunisia"> | <img src="docs/previews/maps/TN.png" width="96" alt="Outline of Tunisia"> |
| **TO** | Tonga | <img src="docs/previews/flags/TO.png" width="80" alt="Flag of Tonga"> | <img src="docs/previews/maps/TO.png" width="96" alt="Outline of Tonga"> |
| **TR** | Turkey | <img src="docs/previews/flags/TR.png" width="80" alt="Flag of Turkey"> | <img src="docs/previews/maps/TR.png" width="96" alt="Outline of Turkey"> |
| **TT** | Trinidad and Tobago | <img src="docs/previews/flags/TT.png" width="80" alt="Flag of Trinidad and Tobago"> | <img src="docs/previews/maps/TT.png" width="96" alt="Outline of Trinidad and Tobago"> |
| **TV** | Tuvalu | <img src="docs/previews/flags/TV.png" width="80" alt="Flag of Tuvalu"> | — |
| **TZ** | Tanzania | <img src="docs/previews/flags/TZ.png" width="80" alt="Flag of Tanzania"> | <img src="docs/previews/maps/TZ.png" width="96" alt="Outline of Tanzania"> |
| **UA** | Ukraine | <img src="docs/previews/flags/UA.png" width="80" alt="Flag of Ukraine"> | <img src="docs/previews/maps/UA.png" width="96" alt="Outline of Ukraine"> |
| **UG** | Uganda | <img src="docs/previews/flags/UG.png" width="80" alt="Flag of Uganda"> | <img src="docs/previews/maps/UG.png" width="96" alt="Outline of Uganda"> |
| **US** | United States | <img src="docs/previews/flags/US.png" width="80" alt="Flag of United States"> | <img src="docs/previews/maps/US.png" width="96" alt="Outline of United States"> |
| **UY** | Uruguay | <img src="docs/previews/flags/UY.png" width="80" alt="Flag of Uruguay"> | <img src="docs/previews/maps/UY.png" width="96" alt="Outline of Uruguay"> |
| **UZ** | Uzbekistan | <img src="docs/previews/flags/UZ.png" width="80" alt="Flag of Uzbekistan"> | <img src="docs/previews/maps/UZ.png" width="96" alt="Outline of Uzbekistan"> |
| **VA** | Vatican City | <img src="docs/previews/flags/VA.png" width="80" alt="Flag of Vatican City"> | <img src="docs/previews/maps/VA.png" width="96" alt="Outline of Vatican City"> |
| **VC** | Saint Vincent and the Grenadines | <img src="docs/previews/flags/VC.png" width="80" alt="Flag of Saint Vincent and the Grenadines"> | <img src="docs/previews/maps/VC.png" width="96" alt="Outline of Saint Vincent and the Grenadines"> |
| **VE** | Venezuela | <img src="docs/previews/flags/VE.png" width="80" alt="Flag of Venezuela"> | <img src="docs/previews/maps/VE.png" width="96" alt="Outline of Venezuela"> |
| **VN** | Vietnam | <img src="docs/previews/flags/VN.png" width="80" alt="Flag of Vietnam"> | <img src="docs/previews/maps/VN.png" width="96" alt="Outline of Vietnam"> |
| **VU** | Vanuatu | <img src="docs/previews/flags/VU.png" width="80" alt="Flag of Vanuatu"> | <img src="docs/previews/maps/VU.png" width="96" alt="Outline of Vanuatu"> |
| **WS** | Samoa | <img src="docs/previews/flags/WS.png" width="80" alt="Flag of Samoa"> | <img src="docs/previews/maps/WS.png" width="96" alt="Outline of Samoa"> |
| **YE** | Yemen | <img src="docs/previews/flags/YE.png" width="80" alt="Flag of Yemen"> | <img src="docs/previews/maps/YE.png" width="96" alt="Outline of Yemen"> |
| **ZA** | South Africa | <img src="docs/previews/flags/ZA.png" width="80" alt="Flag of South Africa"> | <img src="docs/previews/maps/ZA.png" width="96" alt="Outline of South Africa"> |
| **ZM** | Zambia | <img src="docs/previews/flags/ZM.png" width="80" alt="Flag of Zambia"> | <img src="docs/previews/maps/ZM.png" width="96" alt="Outline of Zambia"> |
| **ZW** | Zimbabwe | <img src="docs/previews/flags/ZW.png" width="80" alt="Flag of Zimbabwe"> | <img src="docs/previews/maps/ZW.png" width="96" alt="Outline of Zimbabwe"> |

<!-- GALLERY:END -->

---

## Credits

- Flags — [lipis/flag-icons](https://github.com/lipis/flag-icons), MIT License.
- Outlines — [djaiss/mapsicon](https://github.com/djaiss/mapsicon) by **David Jaiss**,
  used with attribution. Not licensed for resale.
