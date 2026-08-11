"""
Round-trip verification for the generated library.

    python tools/verify.py [--sheet out.png] [CODE ...]

Parses the emitted .cpp files as text, decodes the byte arrays using LVGL's
own I4 rules, and renders the result. This deliberately re-reads the generated
C source rather than the in-memory data, so it catches emission bugs (wrong
dimensions in CA_DEFINE_IMG, truncated arrays, bad stride) and not just
packing bugs.

Decoding rules, taken from LVGL source:
  - data = [16 palette entries x 4 bytes: B, G, R, A][pixel rows]
  - stride = (w + 1) / 2 bytes, EXCLUDING the palette
  - shift  = 4 - 4 * (x & 1)   -> leftmost pixel is the HIGH nibble
    (lv_img_buf.c INDEXED_4BIT in v8; lv_bin_decoder.c LV_COLOR_FORMAT_I4 in v9)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "src"
PALETTE_BYTES = 16 * 4

ARRAY_RE = re.compile(
    r"static\s+const\s+MNF_IMG_ATTR\s+uint8_t\s+(\w+)_data\[(\d+)\]\s*=\s*\{(.*?)\};",
    re.S,
)
DEFINE_RE = re.compile(r"MNF_DEFINE_IMG\(\s*(\w+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,")


def parse_generated() -> dict[str, dict]:
    """Return {symbol: {w, h, data}} for every image in the generated sources."""
    images: dict[str, dict] = {}
    for path in sorted(LIB.glob("*_data_*.cpp")):
        text = path.read_text(encoding="utf-8")

        dims = {m.group(1): (int(m.group(2)), int(m.group(3)))
                for m in DEFINE_RE.finditer(text)}

        for m in ARRAY_RE.finditer(text):
            sym, declared_len, body = m.group(1), int(m.group(2)), m.group(3)
            data = bytes(int(tok, 16) for tok in re.findall(r"0x([0-9A-Fa-f]{2})", body))
            if len(data) != declared_len:
                raise SystemExit(
                    f"{path.name}: {sym} declares [{declared_len}] but has {len(data)} bytes"
                )
            if sym not in dims:
                raise SystemExit(f"{path.name}: {sym} has an array but no MNF_DEFINE_IMG")
            w, h = dims[sym]
            images[sym] = {"w": w, "h": h, "data": data, "file": path.name}
    return images


def decode_i4(w: int, h: int, data: bytes) -> np.ndarray:
    """Decode an LVGL I4 blob to an (h, w, 4) RGBA array."""
    stride = (w + 1) // 2
    expected = PALETTE_BYTES + stride * h
    if len(data) != expected:
        raise ValueError(f"expected {expected} bytes for {w}x{h}, got {len(data)}")

    # Palette is stored B, G, R, A.
    pal = np.frombuffer(data[:PALETTE_BYTES], dtype=np.uint8).reshape(16, 4)
    rgba_pal = np.stack([pal[:, 2], pal[:, 1], pal[:, 0], pal[:, 3]], axis=1)

    px = np.frombuffer(data[PALETTE_BYTES:], dtype=np.uint8).reshape(h, stride)
    hi = px >> 4
    lo = px & 0x0F
    interleaved = np.empty((h, stride * 2), dtype=np.uint8)
    interleaved[:, 0::2] = hi   # leftmost pixel = high nibble
    interleaved[:, 1::2] = lo
    indices = interleaved[:, :w]

    return rgba_pal[indices]


def composite(rgba: np.ndarray, bg: tuple[int, int, int]) -> Image.Image:
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    fg = rgba[:, :, :3].astype(np.float32)
    back = np.array(bg, dtype=np.float32)[None, None, :]
    out = (fg * a + back * (1 - a)).astype(np.uint8)
    return Image.fromarray(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", help="ISO codes to put on the sheet")
    ap.add_argument("--sheet", default=str(ROOT / "build" / "verify_sheet.png"))
    ap.add_argument("--zoom", type=int, default=2)
    args = ap.parse_args()

    images = parse_generated()
    print(f"parsed {len(images)} images from {LIB}")

    # Decode every single one -- this is the real test.
    bad = []
    total = 0
    for sym, rec in images.items():
        try:
            decode_i4(rec["w"], rec["h"], rec["data"])
            total += len(rec["data"])
        except Exception as e:  # noqa: BLE001
            bad.append(f"{sym} ({rec['file']}): {e}")

    if bad:
        print(f"\nFAILED to decode {len(bad)} images:")
        for b in bad[:20]:
            print("  " + b)
        sys.exit(1)
    print(f"all {len(images)} images decode cleanly, {total:,} bytes total")

    codes = [c.lower() for c in args.codes] or [
        "fr", "jp", "us", "gb", "br", "in", "np", "ch", "mx", "za", "kr", "se",
    ]

    Z = args.zoom
    cell_w, cell_h = 0, 0
    tiles = []
    for code in codes:
        for kind, bg in (("flag", (255, 255, 255)), ("map", (245, 245, 248))):
            rec = images.get(f"mnf_{kind}_{code}")
            if rec is None:
                continue
            img = composite(decode_i4(rec["w"], rec["h"], rec["data"]), bg)
            img = img.resize((rec["w"] * Z, rec["h"] * Z), Image.NEAREST)
            tiles.append((f"{code.upper()} {kind}", img))
            cell_w = max(cell_w, img.width)
            cell_h = max(cell_h, img.height)

    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad,
                              rows * (cell_h + pad + 14) + pad), (60, 60, 66))
    dr = ImageDraw.Draw(sheet)
    for i, (label, img) in enumerate(tiles):
        x = pad + (i % cols) * (cell_w + pad)
        y = pad + (i // cols) * (cell_h + pad + 14)
        sheet.paste(img, (x + (cell_w - img.width) // 2, y + (cell_h - img.height) // 2))
        dr.text((x + 2, y + cell_h + 2), label, fill=(235, 235, 235))

    out = Path(args.sheet)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
