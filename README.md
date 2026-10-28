# map-n-flag

Country flags and map silhouettes for **195 countries**, **51 US states**
(+ DC), a full **52-card deck** and the **26 hands of the ASL fingerspelling
alphabet**, baked into flash as plain C++ arrays for the ESP32. No runtime SVG parsing, no SD card, no external asset loading —
everything is `const` data in `.rodata`.

Built for a 320×240 ESP32 "Cheap Yellow Display" (ILI9341, 4 MB flash, no PSRAM),
but there is nothing board-specific in the library.

- **Zero RAM.** `.bss` and `.data` are both 0 bytes — verified with `xtensa-esp32-elf-size`.
- **No LVGL required.** The core has no dependency beyond `stdint.h`. Draw with
  TFT_eSPI, LovyanGFX, or anything else. LVGL v8/v9 support is an optional header.
- **1.09 MiB** of flash for all 195 flags *and* 191 outlines.
- **280 KiB** more for 51 US state flags and outlines (opt-in, both commercially safe).
- **85 KiB** more for the 52-card deck and its back (opt-in, drawn here, so
  there is nothing to attribute).
- **52 KiB** for the ASL alphabet, A to Z (opt-in, public domain).

```cpp
#include "map_n_flag.h"

const mnf_img_t *flag = mnf_flag("FR");   // 80x60 indexed image
const mnf_img_t *map  = mnf_map("FR");    // silhouette, same ISO code
const char      *name = mnf_name("FR");   // "France"

// US states -- same image format, separate lookup
const mnf_img_t *sf = mnf_state_flag("CA");   // California flag
const mnf_img_t *sm = mnf_state_map("CA");    // California outline
const char      *sn = mnf_state_name("CA");   // "California"

// Playing cards -- rank then suit, 48x64, transparent corners
const mnf_img_t *card = mnf_card("AS");       // ace of spades
const mnf_img_t *back = mnf_card_back();      // the card back
const char      *cn   = mnf_card_name("TD");  // "Ten of Diamonds"

// ASL fingerspelling -- one hand per letter, line art, alpha ramp
const mnf_img_t *hand = mnf_sign('A');
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

### Playing card API

A full 52-card deck plus a card back, in the same image format. Cards are keyed
by a 2-character code — rank then suit — so lookup is the same binary search:

```
rank  A 2 3 4 5 6 7 8 9 T J Q K      T is the ten
suit  S H D C                        spades hearts diamonds clubs
```

`"AS"` is the ace of spades, `"TD"` the ten of diamonds. All functions return
`NULL`/`0` if `GENERATE_CARDS` was off at build time.

```cpp
// --- playing cards ------------------------------------------------------
size_t            mnf_card_count(void);                      // 52
const mnf_card_t *mnf_card_at(size_t index);                 // sorted by code
const mnf_card_t *mnf_card_find(const char *code);           // "AS" or "as"
const mnf_card_t *mnf_card_by(uint8_t rank, uint8_t suit);   // 1-13, MNF_SUIT_*
const mnf_img_t  *mnf_card(const char *code);                // the face
const char       *mnf_card_name(const char *code);           // "Ace of Spades"
const mnf_img_t  *mnf_card_back(void);                       // the back
bool              mnf_card_is_red(const mnf_card_t *card);
```

```cpp
typedef struct {
    const char *code;         // "AS"
    const char *name;         // "Ace of Spades"
    const mnf_img_t *img;     // the face, NULL if not generated
    uint8_t rank;             // 1 = ace ... 13 = king, 0 for a joker
    uint8_t suit;             // MNF_SUIT_SPADES / HEARTS / DIAMONDS / CLUBS
} mnf_card_t;
```

Unlike flags, card corners are **transparent** — palette slot 0 — so the rounded
corners composite onto whatever is behind them. Draw with `mnf_row_rgb565()` and
pass your table colour as `bg565`:

```cpp
static uint16_t row[MNF_CARD_WIDTH];
const uint16_t felt = mnf_rgb565(0x16, 0x5C, 0x3C);

void draw_card(const char *code, int16_t x, int16_t y) {
    const mnf_img_t *c = mnf_card(code);
    if (!c) return;
    for (uint16_t ry = 0; ry < c->h; ry++) {
        mnf_row_rgb565(c, ry, row, felt);
        tft.pushImage(x, y + ry, c->w, 1, row);
    }
}
```

Dealing a shuffled deck is index arithmetic over the sorted table — there is no
deck object and nothing to allocate:

```cpp
uint8_t order[52];
for (uint8_t i = 0; i < 52; i++) order[i] = i;
for (uint8_t i = 51; i > 0; i--) {            // Fisher-Yates
    uint8_t j = random(i + 1);
    uint8_t t = order[i]; order[i] = order[j]; order[j] = t;
}
const mnf_card_t *top = mnf_card_at(order[0]);
Serial.println(top->name);
```

See [examples/CardDemo](examples/CardDemo/CardDemo.ino) for a complete sketch.

The artwork is drawn by `tools/render_cards.py` from vector primitives — no
upstream SVG set, no font — so the deck adds nothing to attribute. At 48x64 a
card is 1,600 bytes; the deck, its back and the lookup table come to **85.0 KiB**.
There is no court-card art at this size: jacks, queens and kings show a large
rank letter over their suit, which stays readable where a miniature portrait
would not.

### ASL fingerspelling API

One hand per letter of the American Sign Language manual alphabet, A to Z.
Each is black line art on a transparent page, stored as an alpha ramp like the
state outlines, so `mnf_row_rgb565_tint()` draws it in any ink on any
background. All functions return `NULL`/`0` if `GENERATE_SIGNS` was off.

```cpp
size_t               mnf_sign_count(void);              // 26
const mnf_sign_t    *mnf_sign_at(size_t index);         // 0 is 'A'
const mnf_sign_t    *mnf_sign_find(char letter);        // 'A' or 'a'
const mnf_img_t     *mnf_sign(char letter);             // NULL if not a letter
```

`mnf_sign_t` carries the letter, the image and a `moves` flag. J and Z are
traced in the air rather than held; their drawings show the motion as an
arrow, and `moves` lets a caller say so in words too.

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

### US states (opt-in)

| | Count | Flash |
|---|---|---|
| State flags @ 80×60 | 51 | 122.7 KiB |
| State outlines @ ≤96 px | 51 | 157.9 KiB |
| **State total** | **102** | **280.6 KiB (0.27 MiB)** |

### Playing cards (opt-in)

| | Count | Flash |
|---|---|---|
| Card faces @ 48×64 | 52 | 81.3 KiB |
| Card back @ 48×64 | 1 | 1.6 KiB |
| Lookup table + descriptors | — | 2.2 KiB |
| **Card total** | **53** | **85.0 KiB** |

### ASL hands (opt-in)

| | Count | Flash |
|---|---|---|
| Hands, fit inside 64×84 | 26 | 52.0 KiB |

| | Flash |
|---|---|
| Code (`.text`) | ~1.5 KiB |
| **RAM (`.bss` + `.data`)** | **0 bytes** |

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
| `MAP_BOX` | `96` | Max state outline dimension |
| `MAP_INK` | navy | Baked silhouette colour (overridable at draw time) |
| `TU_SPLIT` | `4` | Number of generated `.cpp` files |
| `GENERATE_STATES` | `True` | Include US state flags and maps |
| `GENERATE_STATE_MAPS` | `True` | Include state outline maps |
| `GENERATE_CARDS` | `True` | Include the playing-card deck |
| `CARD_W` / `CARD_H` | `48` / `64` | Card resolution |
| `CARD_JOKERS` | `False` | Add the two jokers, `"ZR"` and `"ZB"` |
| `GENERATE_SIGNS` | `True` | Include the ASL fingerspelling hands |
| `SIGN_W` / `SIGN_H` | `64` / `84` | Box each hand is fitted inside |

US states add ~280 KiB (122.7 KiB flags + 157.9 KiB maps). Set
`GENERATE_STATES = False` to exclude them entirely. Playing cards add 85.0 KiB;
set `GENERATE_CARDS = False` to drop them.

Cards need no upstream artwork, so they can be rebuilt on their own without
cloning the flag repos — useful when you are only retuning `CARD_W`/`CARD_H`:

```bash
python tools/render_cards.py --sheet build/cards.png   # draw and eyeball them
python tools/build.py --cards-only                     # regenerate just the deck
python tools/verify.py --cards --sheet build/deck.png  # decode the result back
```

The hands need nothing from `vendor/` except the 26 hand SVGs, which
`fetch_sources.py` downloads from Wikimedia Commons:

```bash
python tools/build.py --signs-only
python tools/verify.py --signs    # every hand at 1x and 2x, light and dark
```

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

**Outline cropping.** Each state silhouette is cropped to its tight bounding box
before scaling to fit `MAP_BOX`. Read `img->w` / `img->h` for real dimensions;
`MNF_MAP_BOX` is only the maximum.

---

## Licensing

The **pipeline and library code** in this repo are MIT (see `LICENSE`).
The **artwork** comes from the following upstream projects:

| Asset set | Source | License | Commercial? |
|---|---|---|---|
| Country flags | [lipis/flag-icons](https://github.com/lipis/flag-icons) | **MIT** | ✅ Yes |
| US state flags | [fonttools/region-flags](https://github.com/fonttools/region-flags) | **Public domain** | ✅ Yes |
| US state outlines | [Natural Earth](https://www.naturalearthdata.com/) | **Public domain** | ✅ Yes |
| Playing cards | drawn by `tools/render_cards.py` | **MIT** (this repo) | ✅ Yes |
| ASL hands | [WPClipart via Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Sign_language_A.svg) | **Public domain (CC0)** | ✅ Yes |

All artwork used in this library is commercially safe. Country flags are MIT
licensed, US state flags are public domain, US state outlines come from Natural
Earth (public domain), the playing cards are drawn from vector primitives in
this repo, so they carry no upstream licence at all, and the ASL hands are
WPClipart's public-domain set. See `NOTICE.md` for details.

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

### Playing cards

<!-- CARD_GALLERY:START -->

The full deck, 48x64 each, decoded from the generated C arrays. Corners are transparent, so they are shown here on felt green rather than white.

| Suit | A | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | T | J | Q | K |
|:----:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Spades** | <img src="docs/previews/cards/AS.png" width="48" alt="Ace of Spades"> | <img src="docs/previews/cards/2S.png" width="48" alt="Two of Spades"> | <img src="docs/previews/cards/3S.png" width="48" alt="Three of Spades"> | <img src="docs/previews/cards/4S.png" width="48" alt="Four of Spades"> | <img src="docs/previews/cards/5S.png" width="48" alt="Five of Spades"> | <img src="docs/previews/cards/6S.png" width="48" alt="Six of Spades"> | <img src="docs/previews/cards/7S.png" width="48" alt="Seven of Spades"> | <img src="docs/previews/cards/8S.png" width="48" alt="Eight of Spades"> | <img src="docs/previews/cards/9S.png" width="48" alt="Nine of Spades"> | <img src="docs/previews/cards/TS.png" width="48" alt="Ten of Spades"> | <img src="docs/previews/cards/JS.png" width="48" alt="Jack of Spades"> | <img src="docs/previews/cards/QS.png" width="48" alt="Queen of Spades"> | <img src="docs/previews/cards/KS.png" width="48" alt="King of Spades"> |
| **Hearts** | <img src="docs/previews/cards/AH.png" width="48" alt="Ace of Hearts"> | <img src="docs/previews/cards/2H.png" width="48" alt="Two of Hearts"> | <img src="docs/previews/cards/3H.png" width="48" alt="Three of Hearts"> | <img src="docs/previews/cards/4H.png" width="48" alt="Four of Hearts"> | <img src="docs/previews/cards/5H.png" width="48" alt="Five of Hearts"> | <img src="docs/previews/cards/6H.png" width="48" alt="Six of Hearts"> | <img src="docs/previews/cards/7H.png" width="48" alt="Seven of Hearts"> | <img src="docs/previews/cards/8H.png" width="48" alt="Eight of Hearts"> | <img src="docs/previews/cards/9H.png" width="48" alt="Nine of Hearts"> | <img src="docs/previews/cards/TH.png" width="48" alt="Ten of Hearts"> | <img src="docs/previews/cards/JH.png" width="48" alt="Jack of Hearts"> | <img src="docs/previews/cards/QH.png" width="48" alt="Queen of Hearts"> | <img src="docs/previews/cards/KH.png" width="48" alt="King of Hearts"> |
| **Diamonds** | <img src="docs/previews/cards/AD.png" width="48" alt="Ace of Diamonds"> | <img src="docs/previews/cards/2D.png" width="48" alt="Two of Diamonds"> | <img src="docs/previews/cards/3D.png" width="48" alt="Three of Diamonds"> | <img src="docs/previews/cards/4D.png" width="48" alt="Four of Diamonds"> | <img src="docs/previews/cards/5D.png" width="48" alt="Five of Diamonds"> | <img src="docs/previews/cards/6D.png" width="48" alt="Six of Diamonds"> | <img src="docs/previews/cards/7D.png" width="48" alt="Seven of Diamonds"> | <img src="docs/previews/cards/8D.png" width="48" alt="Eight of Diamonds"> | <img src="docs/previews/cards/9D.png" width="48" alt="Nine of Diamonds"> | <img src="docs/previews/cards/TD.png" width="48" alt="Ten of Diamonds"> | <img src="docs/previews/cards/JD.png" width="48" alt="Jack of Diamonds"> | <img src="docs/previews/cards/QD.png" width="48" alt="Queen of Diamonds"> | <img src="docs/previews/cards/KD.png" width="48" alt="King of Diamonds"> |
| **Clubs** | <img src="docs/previews/cards/AC.png" width="48" alt="Ace of Clubs"> | <img src="docs/previews/cards/2C.png" width="48" alt="Two of Clubs"> | <img src="docs/previews/cards/3C.png" width="48" alt="Three of Clubs"> | <img src="docs/previews/cards/4C.png" width="48" alt="Four of Clubs"> | <img src="docs/previews/cards/5C.png" width="48" alt="Five of Clubs"> | <img src="docs/previews/cards/6C.png" width="48" alt="Six of Clubs"> | <img src="docs/previews/cards/7C.png" width="48" alt="Seven of Clubs"> | <img src="docs/previews/cards/8C.png" width="48" alt="Eight of Clubs"> | <img src="docs/previews/cards/9C.png" width="48" alt="Nine of Clubs"> | <img src="docs/previews/cards/TC.png" width="48" alt="Ten of Clubs"> | <img src="docs/previews/cards/JC.png" width="48" alt="Jack of Clubs"> | <img src="docs/previews/cards/QC.png" width="48" alt="Queen of Clubs"> | <img src="docs/previews/cards/KC.png" width="48" alt="King of Clubs"> |

Back: <img src="docs/previews/cards/BK.png" width="48" alt="Card back">

<!-- CARD_GALLERY:END -->

### ASL fingerspelling

<!-- SIGN_GALLERY:START -->

All 26 hands of the ASL manual alphabet. Each is cropped to its own drawing and fits a 64x84 box; J and Z are motions and their drawings carry the motion as an arrow.

|   |   |   |   |   |   |   |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| <img src="docs/previews/signs/A.png" width="64" alt="ASL A"><br>**A** | <img src="docs/previews/signs/B.png" width="64" alt="ASL B"><br>**B** | <img src="docs/previews/signs/C.png" width="64" alt="ASL C"><br>**C** | <img src="docs/previews/signs/D.png" width="64" alt="ASL D"><br>**D** | <img src="docs/previews/signs/E.png" width="64" alt="ASL E"><br>**E** | <img src="docs/previews/signs/F.png" width="64" alt="ASL F"><br>**F** | <img src="docs/previews/signs/G.png" width="64" alt="ASL G"><br>**G** |
| <img src="docs/previews/signs/H.png" width="64" alt="ASL H"><br>**H** | <img src="docs/previews/signs/I.png" width="64" alt="ASL I"><br>**I** | <img src="docs/previews/signs/J.png" width="64" alt="ASL J"><br>**J** | <img src="docs/previews/signs/K.png" width="64" alt="ASL K"><br>**K** | <img src="docs/previews/signs/L.png" width="64" alt="ASL L"><br>**L** | <img src="docs/previews/signs/M.png" width="64" alt="ASL M"><br>**M** | <img src="docs/previews/signs/N.png" width="64" alt="ASL N"><br>**N** |
| <img src="docs/previews/signs/O.png" width="64" alt="ASL O"><br>**O** | <img src="docs/previews/signs/P.png" width="64" alt="ASL P"><br>**P** | <img src="docs/previews/signs/Q.png" width="64" alt="ASL Q"><br>**Q** | <img src="docs/previews/signs/R.png" width="64" alt="ASL R"><br>**R** | <img src="docs/previews/signs/S.png" width="64" alt="ASL S"><br>**S** | <img src="docs/previews/signs/T.png" width="64" alt="ASL T"><br>**T** | <img src="docs/previews/signs/U.png" width="64" alt="ASL U"><br>**U** |
| <img src="docs/previews/signs/V.png" width="64" alt="ASL V"><br>**V** | <img src="docs/previews/signs/W.png" width="64" alt="ASL W"><br>**W** | <img src="docs/previews/signs/X.png" width="64" alt="ASL X"><br>**X** | <img src="docs/previews/signs/Y.png" width="64" alt="ASL Y"><br>**Y** | <img src="docs/previews/signs/Z.png" width="64" alt="ASL Z"><br>**Z** |   |   |

<!-- SIGN_GALLERY:END -->

---

## Credits

- Country flags — [lipis/flag-icons](https://github.com/lipis/flag-icons), MIT License.
- US state flags — [fonttools/region-flags](https://github.com/fonttools/region-flags),
  public domain (Wikipedia).
- US state outlines — [Natural Earth](https://www.naturalearthdata.com/), public domain.
- Playing cards — drawn by [`tools/render_cards.py`](tools/render_cards.py); no upstream artwork.
- ASL hands — WPClipart's "American ABCs" set, via
  [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Sign_language_A.svg), public domain (CC0).
