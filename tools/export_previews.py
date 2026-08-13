"""
Export PNG previews of every generated image and rebuild the README gallery.

    python tools/export_previews.py

Decodes the *generated C source* (not the intermediate build data), so the
previews show exactly what the device will draw. Writes:

    docs/previews/flags/<CODE>.png         country flag on white, 1px border
    docs/previews/maps/<CODE>.png          country outline centred
    docs/previews/state_flags/<CODE>.png   US state flag on white, 1px border
    docs/previews/state_maps/<CODE>.png    US state outline centred

and rewrites the tables in README.md between the GALLERY markers.
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
from states_data import US_STATES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "docs" / "previews"
README = ROOT / "README.md"

START = "<!-- GALLERY:START -->"
END = "<!-- GALLERY:END -->"
STATE_START = "<!-- STATE_GALLERY:START -->"
STATE_END = "<!-- STATE_GALLERY:END -->"

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


def export_set(
    images: dict,
    codes: list[str],
    names: dict[str, str],
    flag_prefix: str,
    map_prefix: str,
    flag_dir: Path,
    map_dir: Path,
    img_flag_path: str,
    img_map_path: str,
) -> tuple[list[tuple], int, int]:
    """Export flag/map PNGs for a set of codes, return (rows, n_written, total_bytes)."""
    flag_dir.mkdir(parents=True, exist_ok=True)
    map_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    n_written = 0
    total_bytes = 0

    for code in codes:
        lc = code.lower()
        flag_rec = images.get(f"{flag_prefix}{lc}")
        map_rec = images.get(f"{map_prefix}{lc}")

        flag_md = ""
        if flag_rec is not None:
            im = composite_on(decode_i4(flag_rec["w"], flag_rec["h"], flag_rec["data"]), FLAG_BG)
            out = framed(im, config.FLAG_W, config.FLAG_H, FLAG_BG)
            p = flag_dir / f"{code}.png"
            out.save(p, optimize=True)
            total_bytes += p.stat().st_size
            n_written += 1
            flag_md = (
                f'<img src="{img_flag_path}/{code}.png" '
                f'width="{config.FLAG_W}" alt="Flag of {names.get(code, code)}">'
            )

        map_md = "—"
        if map_rec is not None:
            im = composite_on(decode_i4(map_rec["w"], map_rec["h"], map_rec["data"]), MAP_BG)
            out = framed(im, config.MAP_BOX, config.MAP_BOX, MAP_BG)
            p = map_dir / f"{code}.png"
            out.save(p, optimize=True)
            total_bytes += p.stat().st_size
            n_written += 1
            map_md = (
                f'<img src="{img_map_path}/{code}.png" '
                f'width="{config.MAP_BOX}" alt="Outline of {names.get(code, code)}">'
            )

        rows.append((code, names.get(code, code), flag_md, map_md))

    return rows, n_written, total_bytes


def main() -> None:
    images = parse_generated()
    print(f"parsed {len(images)} images")

    country_names = {code: name for code, name, _un, _cur in COUNTRIES}
    state_names = {abbr: name for abbr, name in US_STATES}

    # --- countries --------------------------------------------------------
    country_codes = sorted({
        sym.split("_")[-1].upper()
        for sym in images if sym.startswith("mnf_flag_") and not sym.startswith("mnf_state_flag_")
    })

    country_rows, n1, b1 = export_set(
        images, country_codes, country_names,
        "mnf_flag_", "mnf_map_",
        PREVIEW_DIR / "flags", PREVIEW_DIR / "maps",
        "docs/previews/flags", "docs/previews/maps",
    )
    print(f"countries: {n1} PNGs, {b1/1024:.0f} KiB")

    # --- states -----------------------------------------------------------
    state_codes = sorted({
        sym.removeprefix("mnf_state_flag_").upper()
        for sym in images if sym.startswith("mnf_state_flag_")
    })

    state_rows, n2, b2 = export_set(
        images, state_codes, state_names,
        "mnf_state_flag_", "mnf_state_map_",
        PREVIEW_DIR / "state_flags", PREVIEW_DIR / "state_maps",
        "docs/previews/state_flags", "docs/previews/state_maps",
    )
    print(f"states:    {n2} PNGs, {b2/1024:.0f} KiB")
    print(f"total:     {n1+n2} PNGs, {(b1+b2)/1024:.0f} KiB")

    # --- build country gallery markdown -----------------------------------
    country_md = [
        f"All {len(country_rows)} countries in the current build "
        f"(`SCOPE = \"{config.SCOPE}\"`). Flags are {config.FLAG_W}x{config.FLAG_H}; "
        f"outlines are cropped to their own bounding box and shown centred in a "
        f"{config.MAP_BOX}x{config.MAP_BOX} square. These PNGs are decoded from the "
        f"generated C arrays, so they are exactly what the device draws.",
        "",
        "| Code | Country | Flag | Outline |",
        "|:----:|:--------|:----:|:-------:|",
    ]
    for code, name, flag_md, map_md in country_rows:
        country_md.append(f"| **{code}** | {name} | {flag_md} | {map_md} |")

    # --- build state gallery markdown -------------------------------------
    state_md_lines = [
        f"All {len(state_rows)} US states (+ DC). Same format as above.",
        "",
        "| Code | State | Flag | Outline |",
        "|:----:|:------|:----:|:-------:|",
    ]
    for code, name, flag_md, map_md in state_rows:
        state_md_lines.append(f"| **{code}** | {name} | {flag_md} | {map_md} |")

    # --- update README.md -------------------------------------------------
    text = README.read_text(encoding="utf-8")

    if START in text and END in text:
        head, rest = text.split(START, 1)
        _, tail = rest.split(END, 1)
        text = f"{head}{START}\n\n" + "\n".join(country_md) + f"\n\n{END}{tail}"

    if STATE_START in text and STATE_END in text:
        head, rest = text.split(STATE_START, 1)
        _, tail = rest.split(STATE_END, 1)
        text = f"{head}{STATE_START}\n\n" + "\n".join(state_md_lines) + f"\n\n{STATE_END}{tail}"

    README.write_text(text, encoding="utf-8")
    print(f"updated {README} gallery ({len(country_rows)} countries, {len(state_rows)} states)")


if __name__ == "__main__":
    main()
