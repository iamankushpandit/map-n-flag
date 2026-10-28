"""
map-n-flag build pipeline.

    python tools/build.py            # full rebuild using tools/config.py
    python tools/build.py --report   # size report only, writes nothing

Reads SVG flags from vendor/flag-icons and emits a plain C++ library under src/.

Everything ends up in 4-bit indexed format (I4):

    [16 palette entries x 4 bytes: B, G, R, A][4bpp pixel rows, byte aligned]

Two pixels per byte, leftmost pixel in the HIGH nibble, each row padded up to a
whole byte. That is byte-for-byte what LVGL v8 and v9 both expect, so the same
blob feeds LVGL (via map_n_flag_lvgl.h) or a direct blitter with no conversion.
The generated core has no LVGL dependency at all.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from cards_data import deck as card_deck  # noqa: E402
from countries_data import COUNTRIES  # noqa: E402
from signs_data import SIGNS  # noqa: E402
from states_data import US_STATES  # noqa: E402
from templates import HEADER_TEMPLATE, IMPL_SOURCE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FLAG_SVG_DIR = ROOT / "vendor" / "flag-icons" / "flags" / "4x3"
STATE_FLAG_SVG_DIR = ROOT / "vendor" / "region-flags" / "svg"
STATE_MAP_DIR = ROOT / "build" / "state_maps"
CARD_DIR = ROOT / "build" / "cards"
SIGN_SVG_DIR = ROOT / "vendor" / "asl-wpclipart"
SIGN_RAW_DIR = ROOT / "build" / "signs_raw"
BUILD_DIR = ROOT / "build"
OUT_DIR = ROOT / "src"

PALETTE_ENTRIES = 16  # fixed by I4


# ---------------------------------------------------------------------------
# Image -> I4 conversion
# ---------------------------------------------------------------------------
@dataclass
class Indexed:
    w: int
    h: int
    palette: list[tuple[int, int, int, int]]  # RGBA
    indices: np.ndarray                       # (h, w) uint8, values 0..15


def quantize_rgba(rgba: np.ndarray) -> Indexed:
    """Quantise an RGBA image to at most 16 palette entries.

    If any pixel is transparent, palette slot 0 is reserved as fully
    transparent and the opaque pixels share the remaining 15 slots.
    """
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    transparent = alpha < 128

    has_transparent = bool(transparent.any())
    n_colors = PALETTE_ENTRIES - 1 if has_transparent else PALETTE_ENTRIES

    rgb = rgba[:, :, :3]
    # Quantise only the opaque pixels, so transparent regions (whatever junk
    # colour they carry) do not steal palette slots.
    if has_transparent:
        opaque_pixels = rgb[~transparent]
        if opaque_pixels.size == 0:
            opaque_pixels = np.zeros((1, 3), np.uint8)
        # Pack the opaque pixels into a tall image for PIL to quantise.
        strip = Image.fromarray(opaque_pixels.reshape(-1, 1, 3).astype(np.uint8))
        pal_img = strip.quantize(colors=n_colors, method=Image.MEDIANCUT, dither=Image.NONE)
        palette_rgb = extract_palette(pal_img, n_colors)

        idx = nearest_index(rgb.reshape(-1, 3), palette_rgb).reshape(h, w)
        idx = idx + 1  # shift, slot 0 is the transparent one
        idx[transparent] = 0
        palette = [(0, 0, 0, 0)] + [(r, g, b, 255) for (r, g, b) in palette_rgb]
    else:
        img = Image.fromarray(rgb.astype(np.uint8))
        pal_img = img.quantize(colors=n_colors, method=Image.MEDIANCUT, dither=Image.NONE)
        palette_rgb = extract_palette(pal_img, n_colors)
        idx = np.asarray(pal_img, dtype=np.uint8)
        palette = [(r, g, b, 255) for (r, g, b) in palette_rgb]

    while len(palette) < PALETTE_ENTRIES:
        palette.append((0, 0, 0, 0))

    return Indexed(w=w, h=h, palette=palette, indices=idx.astype(np.uint8))


def extract_palette(pal_img: Image.Image, n_colors: int) -> list[tuple[int, int, int]]:
    """Read a quantised image's palette, padded out to exactly n_colors.

    PIL returns only as many entries as the image actually needed, so a plain
    two-colour flag yields a 2-entry palette. Pad with black rather than
    indexing off the end.
    """
    pal = pal_img.getpalette() or []
    available = len(pal) // 3
    entries = [tuple(pal[i * 3 : i * 3 + 3]) for i in range(min(available, n_colors))]
    while len(entries) < n_colors:
        entries.append((0, 0, 0))
    return entries


def nearest_index(pixels: np.ndarray, palette_rgb: list[tuple[int, int, int]]) -> np.ndarray:
    """Map each RGB pixel to the closest palette entry (squared euclidean)."""
    pal = np.asarray(palette_rgb, dtype=np.int32)          # (n, 3)
    px = pixels.astype(np.int32)                            # (m, 3)
    # (m, n) distance matrix, chunked to bound peak memory on big images.
    out = np.empty(px.shape[0], dtype=np.uint8)
    CHUNK = 65536
    for s in range(0, px.shape[0], CHUNK):
        block = px[s : s + CHUNK]
        d = ((block[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        out[s : s + CHUNK] = d.argmin(axis=1).astype(np.uint8)
    return out


def alpha_ramp_indexed(alpha: np.ndarray, ink: tuple[int, int, int]) -> Indexed:
    """Turn an 8-bit alpha silhouette into I4 using a 16-step alpha ramp.

    Visually identical to a 4-bit alpha mask, but I4 renders on both the v8 and
    v9 software renderers whereas A4 is GPU-only in v9.
    """
    h, w = alpha.shape
    # Round to nearest of 16 levels rather than truncating, so edges keep their
    # antialiasing instead of darkening.
    idx = ((alpha.astype(np.uint16) * 15 + 127) // 255).astype(np.uint8)
    r, g, b = ink
    palette = [(r, g, b, round(i * 255 / 15)) for i in range(PALETTE_ENTRIES)]
    return Indexed(w=w, h=h, palette=palette, indices=idx)


def pack_i4(img: Indexed) -> bytes:
    """Serialise to LVGL's I4 blob: palette (B,G,R,A) then 4bpp rows."""
    out = bytearray()
    for (r, g, b, a) in img.palette:
        out += bytes((b, g, r, a))  # lv_color32_t is {blue, green, red, alpha}

    for y in range(img.h):
        row = img.indices[y].astype(np.uint8) & 0x0F
        if img.w % 2:
            row = np.append(row, np.uint8(0))  # pad odd widths to a whole byte
        # Leftmost pixel goes in the HIGH nibble (verified against both
        # lv_img_buf.c and lv_bin_decoder.c: shift = 4 - 4 * (x & 1)).
        packed = ((row[0::2] << 4) | row[1::2]).astype(np.uint8)
        out += packed.tobytes()
    return bytes(out)


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------
def load_flag(code: str, raw_dir: Path) -> Indexed | None:
    p = raw_dir / f"{code}.rgba"
    if not p.exists():
        return None
    buf = np.frombuffer(p.read_bytes(), dtype=np.uint8)
    rgba = buf.reshape(config.FLAG_H, config.FLAG_W, 4)
    return quantize_rgba(rgba)


def load_card(code: str, card_dir: Path) -> Indexed | None:
    """Load a rendered card face. The rounded corners are transparent, so slot
    0 of the palette is reserved for them by quantize_rgba()."""
    p = card_dir / f"{code}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    return quantize_rgba(np.asarray(im, dtype=np.uint8))


def load_sign(letter: str, raw_dir: Path) -> Indexed | None:
    """Crop a rendered hand to its ink, thicken it, and fit it in the box.

    The rasteriser renders about eight times larger than the output so that
    the thickening below is a fraction of an output pixel rather than a whole
    one -- a MaxFilter at output size could only ever add a full pixel, which
    turns the fist letters into blots.
    """
    p = raw_dir / f"{letter}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("L")
    box = im.point(lambda v: 255 if v > 8 else 0).getbbox()
    if box is None:
        return None
    im = im.crop(box)

    fit = min(config.SIGN_W / im.width, config.SIGN_H / im.height)
    grow = round(config.SIGN_THICKEN / fit)          # render pixels
    if grow > 0:
        im = im.filter(ImageFilter.MaxFilter(grow * 2 + 1))

    w = max(1, round(im.width * fit))
    h = max(1, round(im.height * fit))
    im = im.resize((w, h), Image.LANCZOS)
    return alpha_ramp_indexed(np.asarray(im, dtype=np.uint8), config.SIGN_INK)


def load_state_map(code: str, state_map_dir: Path) -> Indexed | None:
    p = state_map_dir / f"{code}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("L")
    return alpha_ramp_indexed(np.asarray(im, dtype=np.uint8), config.MAP_INK)


# ---------------------------------------------------------------------------
# C++ emission
# ---------------------------------------------------------------------------
def c_array_body(data: bytes, indent: str = "    ") -> str:
    lines = []
    n = config.BYTES_PER_LINE
    for i in range(0, len(data), n):
        chunk = data[i : i + n]
        lines.append(indent + ", ".join(f"0x{b:02X}" for b in chunk) + ",")
    return "\n".join(lines)


ATTRIBUTION = """/*
 * map-n-flag -- generated by tools/build.py. DO NOT EDIT BY HAND.
 * Re-run `python tools/build.py` after changing tools/config.py.
 *
 * Country flag artwork:  lipis/flag-icons          -- MIT License.
 * State flag artwork:    fonttools/region-flags     -- public domain (Wikipedia).
 * State map artwork:     Natural Earth              -- public domain.
 * Playing cards:         drawn by tools/render_cards.py -- no upstream art.
 * ASL hand artwork:      WPClipart via Wikimedia Commons -- public domain (CC0).
 */
"""


def emit_data_files(kind: str, items: list[tuple[str, Indexed, bytes]]) -> list[str]:
    """Write mnf_flag_data_N.cpp / mnf_map_data_N.cpp, return (code, symbol)."""
    n_tu = max(1, config.TU_SPLIT)
    buckets: list[list[tuple[str, Indexed, bytes]]] = [[] for _ in range(n_tu)]
    for i, item in enumerate(items):
        buckets[i % n_tu].append(item)

    symbols = []
    for tu, bucket in enumerate(buckets):
        path = OUT_DIR / f"mnf_{kind}_data_{tu}.cpp"
        with path.open("w", encoding="utf-8") as f:
            f.write(ATTRIBUTION)
            f.write('\n#include "map_n_flag.h"\n\n')
            for code, img, blob in bucket:
                sym = f"mnf_{kind}_{code.lower()}"
                f.write(
                    f"static const MNF_IMG_ATTR uint8_t {sym}_data[{len(blob)}] = {{\n"
                    f"{c_array_body(blob)}\n}};\n"
                )
                f.write(f"MNF_DEFINE_IMG({sym}, {img.w}, {img.h}, {sym}_data);\n\n")
                symbols.append((code, sym))
    return symbols


def emit_tables(rows: list[dict], flag_syms: dict, map_syms: dict) -> None:
    path = OUT_DIR / "mnf_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')

        for code, sym in sorted(flag_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")
        for code, sym in sorted(map_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")

        f.write("\n/* Sorted by ISO code so lookup can binary-search. */\n")
        f.write("extern const mnf_country_t mnf_country_table[] = {\n")
        for r in rows:
            code = r["code"]
            fs = f"&{flag_syms[code]}" if code in flag_syms else "NULL"
            ms = f"&{map_syms[code]}" if code in map_syms else "NULL"
            name = r["name"].replace('"', '\\"')
            f.write(f'    {{ "{code}", "{name}", {fs}, {ms} }},\n')
        f.write("};\n\n")
        f.write(f"extern const uint16_t mnf_country_count = {len(rows)};\n")


def emit_state_tables(
    state_rows: list[dict],
    sflag_syms: dict,
    smap_syms: dict,
) -> None:
    path = OUT_DIR / "mnf_state_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')

        for code, sym in sorted(sflag_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")
        for code, sym in sorted(smap_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")

        f.write("\n/* Sorted by abbreviation so lookup can binary-search. */\n")
        f.write("extern const mnf_state_t mnf_state_table[] = {\n")
        for r in state_rows:
            code = r["code"]
            fs = f"&{sflag_syms[code]}" if code in sflag_syms else "NULL"
            ms = f"&{smap_syms[code]}" if code in smap_syms else "NULL"
            name = r["name"].replace('"', '\\"')
            f.write(f'    {{ "{code}", "{name}", {fs}, {ms} }},\n')
        f.write("};\n\n")
        f.write(f"extern const uint16_t mnf_state_count_val = {len(state_rows)};\n")


def emit_card_table(card_rows: list[dict], card_syms: dict, back_sym: str | None) -> None:
    path = OUT_DIR / "mnf_card_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')

        for code, sym in sorted(card_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")
        if back_sym:
            f.write(f"extern const mnf_img_t {back_sym};\n")

        f.write("\n/* Sorted by card code so lookup can binary-search. */\n")
        f.write("extern const mnf_card_t mnf_card_table[] = {\n")
        for r in card_rows:
            code = r["code"]
            img = f"&{card_syms[code]}" if code in card_syms else "NULL"
            name = r["name"].replace('"', '\\"')
            f.write(f'    {{ "{code}", "{name}", {img}, '
                    f'{r["rank"]}, {r["suit"]} }},\n')
        f.write("};\n\n")
        f.write(f"extern const uint16_t mnf_card_count_val = {len(card_rows)};\n")
        f.write("extern const mnf_img_t *const mnf_card_back_img = "
                f"{'&' + back_sym if back_sym else 'NULL'};\n")


def emit_empty_card_table() -> None:
    """Emit a stub card table when GENERATE_CARDS is off."""
    path = OUT_DIR / "mnf_card_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')
        # Fully spelled out rather than { {0} }, so the stub stays quiet
        # under -Wextra (-Wmissing-field-initializers).
        f.write("extern const mnf_card_t mnf_card_table[] = "
                "{ { NULL, NULL, NULL, 0, 0 } };\n")
        f.write("extern const uint16_t mnf_card_count_val = 0;\n")
        f.write("extern const mnf_img_t *const mnf_card_back_img = NULL;\n")


def emit_sign_table(sign_syms: dict) -> None:
    path = OUT_DIR / "mnf_sign_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')

        for letter, sym in sorted(sign_syms.items()):
            f.write(f"extern const mnf_img_t {sym};\n")

        f.write("\n/* A to Z, so a letter's index is its offset from 'A'. */\n")
        f.write("extern const mnf_sign_t mnf_sign_table[] = {\n")
        for letter, moves in SIGNS:
            img = f"&{sign_syms[letter]}" if letter in sign_syms else "NULL"
            f.write(f"    {{ '{letter}', {1 if moves else 0}, {img} }},\n")
        f.write("};\n\n")
        f.write(f"extern const uint16_t mnf_sign_count_val = {len(SIGNS)};\n")


def emit_empty_sign_table() -> None:
    """Emit a stub sign table when GENERATE_SIGNS is off."""
    path = OUT_DIR / "mnf_sign_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')
        # Spelled out, like the card stub, so -Wextra stays quiet.
        f.write("extern const mnf_sign_t mnf_sign_table[] = { { 0, 0, NULL } };\n")
        f.write("extern const uint16_t mnf_sign_count_val = 0;\n")


def emit_empty_state_table() -> None:
    """Emit a stub state table when GENERATE_STATES is off."""
    path = OUT_DIR / "mnf_state_table.cpp"
    with path.open("w", encoding="utf-8") as f:
        f.write(ATTRIBUTION)
        f.write('\n#include "map_n_flag.h"\n\n')
        f.write("extern const mnf_state_t mnf_state_table[] = { {0} };\n")
        f.write("extern const uint16_t mnf_state_count_val = 0;\n")


def emit_header(rows: list[dict], stats: dict, state_stats: dict,
                card_stats: dict, sign_stats: dict) -> None:
    """Render the public header.

    Token replacement rather than str.format(), because the template is full of
    C macro bodies whose braces would otherwise all need escaping.
    """
    total = stats["flag_bytes"] + stats["map_bytes"]
    st_total = state_stats["flag_bytes"] + state_stats["map_bytes"]
    subs = {
        "@@FLAG_W@@": str(config.FLAG_W),
        "@@FLAG_H@@": str(config.FLAG_H),
        "@@MAP_BOX@@": str(config.MAP_BOX),
        "@@SCOPE@@": config.SCOPE,
        "@@N_COUNTRIES@@": str(len(rows)),
        "@@N_FLAGS@@": str(stats["n_flags"]),
        "@@N_MAPS@@": str(stats["n_maps"]),
        "@@FLAG_KIB@@": f"{stats['flag_bytes'] / 1024:.1f}",
        "@@MAP_KIB@@": f"{stats['map_bytes'] / 1024:.1f}",
        "@@TOTAL_KIB@@": f"{total / 1024:.1f}",
        "@@N_STATES@@": str(state_stats["n_states"]),
        "@@N_STATE_FLAGS@@": str(state_stats["n_flags"]),
        "@@N_STATE_MAPS@@": str(state_stats["n_maps"]),
        "@@STATE_FLAG_KIB@@": f"{state_stats['flag_bytes'] / 1024:.1f}",
        "@@STATE_MAP_KIB@@": f"{state_stats['map_bytes'] / 1024:.1f}",
        "@@STATE_TOTAL_KIB@@": f"{st_total / 1024:.1f}",
        "@@HAS_STATES@@": "1" if state_stats["n_states"] > 0 else "0",
        "@@CARD_W@@": str(card_w()),
        "@@CARD_H@@": str(card_h()),
        "@@N_CARDS@@": str(card_stats["n_cards"]),
        "@@CARD_KIB@@": f"{card_stats['card_bytes'] / 1024:.1f}",
        "@@HAS_CARDS@@": "1" if card_stats["n_cards"] > 0 else "0",
        "@@SIGN_W@@": str(config.SIGN_W),
        "@@SIGN_H@@": str(config.SIGN_H),
        "@@N_SIGNS@@": str(sign_stats["n_signs"]),
        "@@SIGN_KIB@@": f"{sign_stats['sign_bytes'] / 1024:.1f}",
        "@@HAS_SIGNS@@": "1" if sign_stats["n_signs"] > 0 else "0",
    }
    text = HEADER_TEMPLATE
    for k, v in subs.items():
        text = text.replace(k, v)
    (OUT_DIR / "map_n_flag.h").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def select_countries() -> list[dict]:
    rows = []
    for code, name, is_un, is_cur in COUNTRIES:
        if config.SCOPE == "un195" and not is_un:
            continue
        if config.SCOPE == "curated" and not is_cur:
            continue
        rows.append({"code": code, "name": name})
    return sorted(rows, key=lambda r: r["code"])


def select_states() -> list[dict]:
    return [{"code": abbr, "name": name} for abbr, name in US_STATES]


def card_w() -> int:
    return int(getattr(config, "CARD_W", 48))


def card_h() -> int:
    return int(getattr(config, "CARD_H", 64))


def render_cards() -> None:
    """Run render_cards.py to draw the deck at the configured card size."""
    script = ROOT / "tools" / "render_cards.py"
    cmd = [sys.executable, str(script),
           "--w", str(card_w()), "--h", str(card_h()),
           "--out", str(CARD_DIR)]
    if getattr(config, "CARD_JOKERS", False):
        cmd.append("--jokers")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"WARNING: card renderer failed:\n{proc.stderr}")
    else:
        for line in proc.stdout.strip().splitlines():
            print(f"  {line}")


def build_cards() -> tuple[list[dict], list, Indexed | None, dict]:
    """Render and convert the deck. Returns (rows, items, back, stats)."""
    rows = card_deck(jokers=getattr(config, "CARD_JOKERS", False))
    print(f"playing cards: {len(rows)} + back, {card_w()}x{card_h()}")
    render_cards()

    items = []
    for r in rows:
        img = load_card(r["code"], CARD_DIR)
        if img is not None:
            items.append((r["code"], img, pack_i4(img)))

    back = load_card("BK", CARD_DIR)
    card_bytes = sum(len(b) for _, _, b in items)
    if back is not None:
        card_bytes += len(pack_i4(back))

    stats = {"n_cards": len(items), "card_bytes": card_bytes,
             "has_back": back is not None}

    print()
    print("=" * 62)
    print("  PLAYING CARDS")
    print(f"  Cards : {len(items):3d} images  {card_bytes:8,d} B  "
          f"{card_bytes/1024:8.1f} KiB  "
          f"({card_bytes/max(1,len(items)+1):.0f} B avg, back included)")
    print("=" * 62)
    print()
    return rows, items, back, stats


def emit_cards(rows: list[dict], items: list, back: Indexed | None) -> None:
    """Write the card byte arrays and the lookup table."""
    for old in OUT_DIR.glob("mnf_card_data_*.cpp"):
        old.unlink()

    all_items = list(items)
    back_sym = None
    if back is not None:
        all_items.append(("BK", back, pack_i4(back)))
        back_sym = "mnf_card_bk"

    syms = dict(emit_data_files("card", all_items))
    syms.pop("BK", None)
    emit_card_table(rows, syms, back_sym)


def build_signs() -> tuple[list, dict]:
    """Rasterise and convert the ASL hands. Returns (items, stats)."""
    if not SIGN_SVG_DIR.is_dir():
        sys.exit(f"Missing {SIGN_SVG_DIR}. Run: python tools/fetch_sources.py")
    letters = [letter for letter, _ in SIGNS]
    print(f"ASL hands: {len(letters)}, fit {config.SIGN_W}x{config.SIGN_H} I4")

    BUILD_DIR.mkdir(exist_ok=True)
    letters_json = BUILD_DIR / "sign_letters.json"
    letters_json.write_text(json.dumps(letters), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "rasterize_signs.js"),
         str(SIGN_SVG_DIR), str(SIGN_RAW_DIR), str(config.SIGN_H * 8),
         str(letters_json)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"sign rasteriser failed:\n{proc.stderr}")
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    if info["missing"]:
        sys.exit(f"missing hand SVGs: {', '.join(info['missing'])} -- "
                 "run python tools/fetch_sources.py")

    items = []
    for letter in letters:
        img = load_sign(letter, SIGN_RAW_DIR)
        if img is not None:
            items.append((letter, img, pack_i4(img)))

    sign_bytes = sum(len(b) for _, _, b in items)
    print()
    print("=" * 62)
    print("  ASL HANDS")
    print(f"  Hands : {len(items):3d} images  {sign_bytes:8,d} B  "
          f"{sign_bytes/1024:8.1f} KiB  ({sign_bytes/max(1,len(items)):.0f} B avg)")
    print("=" * 62)
    print()
    return items, {"n_signs": len(items), "sign_bytes": sign_bytes}


def emit_signs(items: list) -> None:
    # The images are mnf_asl_a .. mnf_asl_z. Not mnf_sign_<letter>: the T
    # would be mnf_sign_t, which is the name of the table's struct type.
    for old in OUT_DIR.glob("mnf_asl_data_*.cpp"):
        old.unlink()
    emit_sign_table(dict(emit_data_files("asl", items)))


def rasterise_state_maps() -> None:
    """Run render_state_maps.py to generate state outline PNGs."""
    script = ROOT / "tools" / "render_state_maps.py"
    proc = subprocess.run(
        [sys.executable, str(script),
         "--box", str(config.MAP_BOX),
         "--out", str(STATE_MAP_DIR)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"WARNING: state map renderer failed:\n{proc.stderr}")
    else:
        for line in proc.stdout.strip().splitlines():
            print(f"  {line}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="size report only, write nothing")
    ap.add_argument("--scope", choices=["all", "un195", "curated"],
                    help="override config.SCOPE for this run (handy with --report)")
    ap.add_argument("--cards-only", action="store_true",
                    help="regenerate just the playing cards; leaves the flag and "
                         "map sources, the header and map_n_flag.cpp untouched. "
                         "Needs no vendor/ artwork, since cards are drawn here.")
    ap.add_argument("--signs-only", action="store_true",
                    help="regenerate just the ASL hands and their table; leaves "
                         "the flag and map sources, the header and "
                         "map_n_flag.cpp untouched. Needs only vendor/asl-wpclipart.")
    args = ap.parse_args()

    if args.scope:
        config.SCOPE = args.scope

    if args.cards_only:
        if not getattr(config, "GENERATE_CARDS", False):
            sys.exit("GENERATE_CARDS is off in tools/config.py, nothing to do.")
        rows, items, back, _stats = build_cards()
        if args.report:
            print("--report given, nothing written.")
            return
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        emit_cards(rows, items, back)
        print(f"wrote card sources to {OUT_DIR}")
        print("NOTE: map_n_flag.h still carries the card counts from the last "
              "full build; run `python tools/build.py` to refresh them.")
        return

    if args.signs_only:
        if not getattr(config, "GENERATE_SIGNS", False):
            sys.exit("GENERATE_SIGNS is off in tools/config.py, nothing to do.")
        items, _stats = build_signs()
        if args.report:
            print("--report given, nothing written.")
            return
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        emit_signs(items)
        print(f"wrote sign sources to {OUT_DIR}")
        print("NOTE: map_n_flag.h still carries the sign counts from the last "
              "full build; run `python tools/build.py` to refresh them.")
        return

    if not FLAG_SVG_DIR.is_dir():
        sys.exit(f"Missing {FLAG_SVG_DIR}. Run: python tools/fetch_sources.py")

    rows = select_countries()
    print(f"scope={config.SCOPE}: {len(rows)} countries")
    print(f"flags {config.FLAG_W}x{config.FLAG_H} I4, maps fit {config.MAP_BOX}px I4")

    # --- rasterise country flags via sharp --------------------------------
    raw_dir = BUILD_DIR / f"flags_{config.FLAG_W}x{config.FLAG_H}"
    BUILD_DIR.mkdir(exist_ok=True)
    codes_json = BUILD_DIR / "codes.json"
    codes_json.write_text(json.dumps([r["code"] for r in rows]), encoding="utf-8")

    print("rasterising country flags with sharp...")
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "rasterize_flags.js"),
         str(FLAG_SVG_DIR), str(raw_dir), str(config.FLAG_W), str(config.FLAG_H),
         str(codes_json)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"rasteriser failed:\n{proc.stderr}")
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    print(f"  rasterised {info['rasterised']}, missing {len(info['missing'])}")

    # --- convert countries ------------------------------------------------
    flag_items = []
    for r in rows:
        code = r["code"]
        f_img = load_flag(code, raw_dir)
        if f_img is not None:
            flag_items.append((code, f_img, pack_i4(f_img)))

    flag_bytes = sum(len(b) for _, _, b in flag_items)
    stats = {
        "n_flags": len(flag_items), "n_maps": 0,
        "flag_bytes": flag_bytes, "map_bytes": 0,
    }

    print()
    print("=" * 62)
    print("  COUNTRIES")
    print(f"  Flags : {len(flag_items):3d} images  {flag_bytes:8,d} B  "
          f"{flag_bytes/1024:8.1f} KiB  ({flag_bytes/max(1,len(flag_items)):.0f} B avg)")
    print(f"  TOTAL :              {flag_bytes:8,d} B  "
          f"{flag_bytes/1024:8.1f} KiB  "
          f"({flag_bytes/1048576:.2f} MiB)")
    print("=" * 62)
    print()

    # --- US states --------------------------------------------------------
    generate_states = getattr(config, "GENERATE_STATES", False)
    generate_state_maps = getattr(config, "GENERATE_STATE_MAPS", True)

    state_rows: list[dict] = []
    sflag_items: list[tuple[str, Indexed, bytes]] = []
    smap_items: list[tuple[str, Indexed, bytes]] = []
    state_stats = {"n_states": 0, "n_flags": 0, "n_maps": 0,
                   "flag_bytes": 0, "map_bytes": 0}

    if generate_states:
        state_rows = select_states()
        print(f"US states: {len(state_rows)}")

        # Rasterise state flags.
        if STATE_FLAG_SVG_DIR.is_dir():
            state_raw_dir = BUILD_DIR / f"state_flags_{config.FLAG_W}x{config.FLAG_H}"
            state_codes_json = BUILD_DIR / "state_codes.json"
            state_codes_json.write_text(
                json.dumps([r["code"] for r in state_rows]), encoding="utf-8"
            )
            print("rasterising state flags with sharp...")
            proc = subprocess.run(
                ["node", str(ROOT / "tools" / "rasterize_flags.js"),
                 str(STATE_FLAG_SVG_DIR), str(state_raw_dir),
                 str(config.FLAG_W), str(config.FLAG_H),
                 str(state_codes_json), "us-"],
                cwd=ROOT, capture_output=True, text=True,
            )
            if proc.returncode != 0:
                print(f"WARNING: state flag rasteriser failed:\n{proc.stderr}")
            else:
                sinfo = json.loads(proc.stdout.strip().splitlines()[-1])
                print(f"  rasterised {sinfo['rasterised']}, missing {len(sinfo['missing'])}")
                if sinfo["missing"]:
                    print(f"  missing: {', '.join(sinfo['missing'])}")
        else:
            print(f"WARNING: state flag SVG dir not found: {STATE_FLAG_SVG_DIR}")
            print("  Run: python tools/fetch_sources.py")
            state_raw_dir = BUILD_DIR / "state_flags_empty"
            state_raw_dir.mkdir(exist_ok=True)

        # Render state map outlines from Natural Earth.
        if generate_state_maps:
            print("rendering state map outlines from Natural Earth...")
            rasterise_state_maps()

        # Convert state assets.
        missing_state_maps = []
        for r in state_rows:
            code = r["code"]
            f_img = load_flag(code, state_raw_dir)
            if f_img is not None:
                sflag_items.append((code, f_img, pack_i4(f_img)))
            if generate_state_maps:
                m_img = load_state_map(code, STATE_MAP_DIR)
            else:
                m_img = None
            if m_img is not None:
                smap_items.append((code, m_img, pack_i4(m_img)))
            else:
                missing_state_maps.append(code)

        sflag_bytes = sum(len(b) for _, _, b in sflag_items)
        smap_bytes = sum(len(b) for _, _, b in smap_items)
        state_stats = {
            "n_states": len(state_rows),
            "n_flags": len(sflag_items), "n_maps": len(smap_items),
            "flag_bytes": sflag_bytes, "map_bytes": smap_bytes,
        }

        print()
        print("=" * 62)
        print("  US STATES")
        print(f"  Flags : {len(sflag_items):3d} images  {sflag_bytes:8,d} B  "
              f"{sflag_bytes/1024:8.1f} KiB  "
              f"({sflag_bytes/max(1,len(sflag_items)):.0f} B avg)")
        print(f"  Maps  : {len(smap_items):3d} images  {smap_bytes:8,d} B  "
              f"{smap_bytes/1024:8.1f} KiB  "
              f"({smap_bytes/max(1,len(smap_items)):.0f} B avg)")
        stot = sflag_bytes + smap_bytes
        print(f"  TOTAL :              {stot:8,d} B  "
              f"{stot/1024:8.1f} KiB  ({stot/1048576:.2f} MiB)")
        print("=" * 62)
        if missing_state_maps:
            print(f"  no state map: {', '.join(missing_state_maps)}")
        print()

    # --- playing cards ----------------------------------------------------
    generate_cards = getattr(config, "GENERATE_CARDS", False)
    card_rows: list[dict] = []
    card_items: list[tuple[str, Indexed, bytes]] = []
    card_back: Indexed | None = None
    card_stats = {"n_cards": 0, "card_bytes": 0, "has_back": False}

    if generate_cards:
        card_rows, card_items, card_back, card_stats = build_cards()

    # --- ASL hands -------------------------------------------------------
    generate_signs = getattr(config, "GENERATE_SIGNS", False)
    sign_items: list[tuple[str, Indexed, bytes]] = []
    sign_stats = {"n_signs": 0, "sign_bytes": 0}
    if generate_signs:
        sign_items, sign_stats = build_signs()

    if args.report:
        print("--report given, nothing written.")
        return

    # --- emit -----------------------------------------------------------
    if OUT_DIR.exists():
        for old in OUT_DIR.glob("mnf_*_data_*.cpp"):
            old.unlink()
        for old in OUT_DIR.glob("mnf_state_*_data_*.cpp"):
            old.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    emit_header(rows, stats, state_stats, card_stats, sign_stats)
    (OUT_DIR / "map_n_flag.cpp").write_text(IMPL_SOURCE, encoding="utf-8")

    flag_syms = dict(emit_data_files("flag", flag_items))
    map_syms = {}
    emit_tables(rows, flag_syms, map_syms)

    if generate_states and state_rows:
        sflag_syms = dict(emit_data_files("state_flag", sflag_items))
        smap_syms = dict(emit_data_files("state_map", smap_items)) if smap_items else {}
        emit_state_tables(state_rows, sflag_syms, smap_syms)
    else:
        emit_empty_state_table()

    if generate_cards and card_items:
        emit_cards(card_rows, card_items, card_back)
    else:
        emit_empty_card_table()

    if generate_signs and sign_items:
        emit_signs(sign_items)
    else:
        emit_empty_sign_table()

    print(f"wrote {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(f"  {p.name:32s} {p.stat().st_size:9,d} B")


if __name__ == "__main__":
    main()
