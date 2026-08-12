"""
map-n-flag build pipeline.

    python tools/build.py            # full rebuild using tools/config.py
    python tools/build.py --report   # size report only, writes nothing

Reads SVG flags from vendor/flag-icons and silhouette PNGs from
vendor/mapsicon, and emits a plain C++ library under src/.

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
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from countries_data import COUNTRIES  # noqa: E402
from templates import HEADER_TEMPLATE, IMPL_SOURCE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FLAG_SVG_DIR = ROOT / "vendor" / "flag-icons" / "flags" / "4x3"
MAP_DIR = ROOT / "vendor" / "mapsicon" / "all"
BUILD_DIR = ROOT / "build"
OUT_DIR = ROOT / "src"

PALETTE_ENTRIES = 16  # fixed by I4
MAP_SRC = "1024.png"


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


def load_map(code: str) -> Indexed | None:
    p = MAP_DIR / code.lower() / MAP_SRC
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    alpha = im.split()[3]
    bbox = alpha.getbbox()
    if bbox is None:
        return None
    alpha = alpha.crop(bbox)

    box = config.MAP_BOX
    scale = min(box / alpha.width, box / alpha.height)
    w = max(1, round(alpha.width * scale))
    h = max(1, round(alpha.height * scale))
    alpha = alpha.resize((w, h), Image.LANCZOS)

    return alpha_ramp_indexed(np.asarray(alpha, dtype=np.uint8), config.MAP_INK)


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
 * Flag artwork:  lipis/flag-icons          -- MIT License.
 * Map artwork:   djaiss/mapsicon (David Jaiss) -- used with attribution.
 *                "Do what you want with them as long as you mention me in
 *                 your project. Please don't resell them - I forbid it!"
 *                NOT free for commercial resale. See README.md.
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


def emit_header(rows: list[dict], stats: dict) -> None:
    """Render the public header.

    Token replacement rather than str.format(), because the template is full of
    C macro bodies whose braces would otherwise all need escaping.
    """
    total = stats["flag_bytes"] + stats["map_bytes"]
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="size report only, write nothing")
    ap.add_argument("--scope", choices=["all", "un195", "curated"],
                    help="override config.SCOPE for this run (handy with --report)")
    args = ap.parse_args()

    if args.scope:
        config.SCOPE = args.scope

    if not FLAG_SVG_DIR.is_dir():
        sys.exit(f"Missing {FLAG_SVG_DIR}. Run: python tools/fetch_sources.py")
    if not MAP_DIR.is_dir():
        sys.exit(f"Missing {MAP_DIR}. Run: python tools/fetch_sources.py")

    rows = select_countries()
    print(f"scope={config.SCOPE}: {len(rows)} countries")
    print(f"flags {config.FLAG_W}x{config.FLAG_H} I4, maps fit {config.MAP_BOX}px I4")

    # --- rasterise flags via sharp -------------------------------------
    raw_dir = BUILD_DIR / f"flags_{config.FLAG_W}x{config.FLAG_H}"
    BUILD_DIR.mkdir(exist_ok=True)
    codes_json = BUILD_DIR / "codes.json"
    codes_json.write_text(json.dumps([r["code"] for r in rows]), encoding="utf-8")

    print("rasterising flags with sharp...")
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

    # --- convert --------------------------------------------------------
    flag_items, map_items = [], []
    missing_maps = []
    for r in rows:
        code = r["code"]
        f_img = load_flag(code, raw_dir)
        if f_img is not None:
            flag_items.append((code, f_img, pack_i4(f_img)))
        m_img = load_map(code) if getattr(config, "GENERATE_MAPS", True) else None
        if m_img is not None:
            map_items.append((code, m_img, pack_i4(m_img)))
        else:
            missing_maps.append(code)

    flag_bytes = sum(len(b) for _, _, b in flag_items)
    map_bytes = sum(len(b) for _, _, b in map_items)
    stats = {
        "n_flags": len(flag_items), "n_maps": len(map_items),
        "flag_bytes": flag_bytes, "map_bytes": map_bytes,
    }

    print()
    print("=" * 62)
    print(f"  Flags : {len(flag_items):3d} images  {flag_bytes:8,d} B  "
          f"{flag_bytes/1024:8.1f} KiB  ({flag_bytes/max(1,len(flag_items)):.0f} B avg)")
    print(f"  Maps  : {len(map_items):3d} images  {map_bytes:8,d} B  "
          f"{map_bytes/1024:8.1f} KiB  ({map_bytes/max(1,len(map_items)):.0f} B avg)")
    print(f"  TOTAL :              {flag_bytes+map_bytes:8,d} B  "
          f"{(flag_bytes+map_bytes)/1024:8.1f} KiB  "
          f"({(flag_bytes+map_bytes)/1048576:.2f} MiB)")
    print("=" * 62)
    if missing_maps:
        print(f"  no map available: {', '.join(missing_maps)}")
    print()

    if args.report:
        print("--report given, nothing written.")
        return

    # --- emit -----------------------------------------------------------
    if OUT_DIR.exists():
        for old in OUT_DIR.glob("mnf_*_data_*.cpp"):
            old.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    emit_header(rows, stats)
    (OUT_DIR / "map_n_flag.cpp").write_text(IMPL_SOURCE, encoding="utf-8")

    flag_syms = dict(emit_data_files("flag", flag_items))
    # Skip the map translation units entirely when there is nothing to put in
    # them, rather than emitting four empty files.
    map_syms = dict(emit_data_files("map", map_items)) if map_items else {}
    emit_tables(rows, flag_syms, map_syms)

    print(f"wrote {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(f"  {p.name:24s} {p.stat().st_size:9,d} B")


if __name__ == "__main__":
    main()
