"""
Export PNG previews of every generated image and rebuild the README gallery.

    python tools/export_previews.py

Decodes the *generated C source* (not the intermediate build data), so the
previews show exactly what the device will draw. Writes:

    docs/previews/flags/<CODE>.png   flag on white, 1px border
    docs/previews/maps/<CODE>.png    outline centred in a MNF_MAP_BOX square

and rewrites the table in README.md between the GALLERY markers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from verify import decode_i4, parse_generated  # noqa: E402
from countries_data import COUNTRIES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "docs" / "previews"
README = ROOT / "README.md"

START = "<!-- GALLERY:START -->"
END = "<!-- GALLERY:END -->"

FLAG_BG = (255, 255, 255)
MAP_BG = (255, 255, 255)
BORDER = (205, 205, 212)


def composite_on(rgba: np.ndarray, bg: tuple[int, int, int]) -> Image.Image:
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    fg = rgba[:, :, :3].astype(np.float32)
    back = np.array(bg, dtype=np.float32)[None, None, :]
    return Image.fromarray((fg * a + back * (1 - a)).astype(np.uint8))


def framed(img: Image.Image, canvas_w: int, canvas_h: int,
           bg: tuple[int, int, int]) -> Image.Image:
    """Centre img on a bg canvas and draw a 1px border.

    The border matters: Japan and Switzerland are mostly white, and without it
    they dissolve into the page background on GitHub's light theme.
    """
    out = Image.new("RGB", (canvas_w + 2, canvas_h + 2), BORDER)
    inner = Image.new("RGB", (canvas_w, canvas_h), bg)
    inner.paste(img, ((canvas_w - img.width) // 2, (canvas_h - img.height) // 2))
    out.paste(inner, (1, 1))
    return out


def main() -> None:
    images = parse_generated()
    print(f"parsed {len(images)} images")

    (PREVIEW_DIR / "flags").mkdir(parents=True, exist_ok=True)
    (PREVIEW_DIR / "maps").mkdir(parents=True, exist_ok=True)

    names = {code: name for code, name, _un, _cur in COUNTRIES}

    rows = []
    n_written = 0
    total_bytes = 0

    # Walk the generated table order (sorted by ISO code).
    codes = sorted({sym.split("_")[-1].upper()
                    for sym in images if sym.startswith("mnf_flag_")})

    for code in codes:
        lc = code.lower()
        flag_rec = images.get(f"mnf_flag_{lc}")
        map_rec = images.get(f"mnf_map_{lc}")

        flag_md = ""
        if flag_rec is not None:
            im = composite_on(decode_i4(flag_rec["w"], flag_rec["h"], flag_rec["data"]), FLAG_BG)
            out = framed(im, config.FLAG_W, config.FLAG_H, FLAG_BG)
            p = PREVIEW_DIR / "flags" / f"{code}.png"
            out.save(p, optimize=True)
            total_bytes += p.stat().st_size
            n_written += 1
            flag_md = f'<img src="docs/previews/flags/{code}.png" width="{config.FLAG_W}" alt="Flag of {names.get(code, code)}">'

        map_md = "—"
        if map_rec is not None:
            im = composite_on(decode_i4(map_rec["w"], map_rec["h"], map_rec["data"]), MAP_BG)
            out = framed(im, config.MAP_BOX, config.MAP_BOX, MAP_BG)
            p = PREVIEW_DIR / "maps" / f"{code}.png"
            out.save(p, optimize=True)
            total_bytes += p.stat().st_size
            n_written += 1
            map_md = f'<img src="docs/previews/maps/{code}.png" width="{config.MAP_BOX}" alt="Outline of {names.get(code, code)}">'

        rows.append((code, names.get(code, code), flag_md, map_md))

    print(f"wrote {n_written} PNGs, {total_bytes/1024:.0f} KiB total")

    # --- build the markdown table ------------------------------------------
    md = [
        f"All {len(rows)} countries in the current build "
        f"(`SCOPE = \"{config.SCOPE}\"`). Flags are {config.FLAG_W}x{config.FLAG_H}; "
        f"outlines are cropped to their own bounding box and shown centred in a "
        f"{config.MAP_BOX}x{config.MAP_BOX} square. These PNGs are decoded from the "
        f"generated C arrays, so they are exactly what the device draws.",
        "",
        "| Code | Country | Flag | Outline |",
        "|:----:|:--------|:----:|:-------:|",
    ]
    for code, name, flag_md, map_md in rows:
        md.append(f"| **{code}** | {name} | {flag_md} | {map_md} |")

    table = "\n".join(md)

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"README.md is missing the {START} / {END} markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n\n{table}\n\n{END}{tail}", encoding="utf-8")
    print(f"updated {README} gallery ({len(rows)} rows)")


if __name__ == "__main__":
    main()
