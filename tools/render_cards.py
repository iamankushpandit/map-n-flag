"""
Render a standard playing-card deck to PNGs for the build.py I4 pipeline.

    python tools/render_cards.py [--w 48] [--h 64] [--out build/cards] [--jokers]

Everything is drawn here from vector primitives -- there is no upstream
artwork, no SVG source and no font dependency, so the deck carries no
third-party licence. Suit pips come from parametric curves and circles; rank
glyphs come from the stroke paths in GLYPHS below.

Each card is drawn at SUPERSAMPLE x the target size and then filtered down,
which is where the antialiasing comes from. At 48x64 a corner rank is about
13 px tall, so the glyphs are stroked rather than filled outlines -- stencil
strokes stay legible at that size where a text face turns to mush.

Writes <CODE>.png per card plus BK.png (the back), all RGBA with a transparent
surround, so the rounded corners composite over whatever is already on screen.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from cards_data import deck  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SUPERSAMPLE = 8

# Only a handful of colours, which leaves the 16-entry I4 palette plenty of
# room for the antialiased edge ramps -- those are what actually consume slots.
FACE = (255, 255, 255, 255)
EDGE = (96, 100, 112, 255)
RED = (200, 28, 44, 255)
BLACK = (26, 26, 32, 255)
BACK_INK = (26, 50, 120, 255)
BACK_LINE = (255, 255, 255, 255)


# ---------------------------------------------------------------------------
# Geometry helpers. Shapes are defined in a unit square with y pointing down,
# then placed with fit(), which maps that square onto a pixel box.
# ---------------------------------------------------------------------------
def arc(cx: float, cy: float, rx: float, ry: float,
        a0: float, a1: float, n: int = 28) -> list[tuple[float, float]]:
    """Sample an elliptical arc. Angles are degrees, 0 = right, 90 = down."""
    return [
        (cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
        for a in (a0 + (a1 - a0) * i / (n - 1) for i in range(n))
    ]


def circle(cx: float, cy: float, r: float, n: int = 36) -> list[tuple[float, float]]:
    return arc(cx, cy, r, r, 0, 360, n)


def fit(pts, box: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Map unit-square points onto box = (x, y, w, h), in pixels."""
    x, y, w, h = box
    return [(x + px * w, y + py * h) for px, py in pts]


def heart_outline(n: int = 90) -> list[tuple[float, float]]:
    """The classic parametric heart, normalised into the unit square."""
    raw = []
    for i in range(n):
        t = 2 * math.pi * i / n
        raw.append((
            16 * math.sin(t) ** 3,
            13 * math.cos(t) - 5 * math.cos(2 * t)
            - 2 * math.cos(3 * t) - math.cos(4 * t),
        ))
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    # Flip y: the curve is y-up, the canvas is y-down.
    return [((x - x0) / (x1 - x0), 1.0 - (y - y0) / (y1 - y0)) for x, y in raw]


def flip_y(pts) -> list[tuple[float, float]]:
    return [(x, 1.0 - y) for x, y in pts]


def star(points: int = 5, r_out: float = 0.5, r_in: float = 0.21
         ) -> list[tuple[float, float]]:
    pts = []
    for i in range(points * 2):
        a = -90 + i * 180 / points
        r = r_out if i % 2 == 0 else r_in
        pts.append((0.5 + r * math.cos(math.radians(a)),
                    0.5 + r * math.sin(math.radians(a))))
    return pts


# ---------------------------------------------------------------------------
# Suit pips
# ---------------------------------------------------------------------------
def draw_pip(dr: ImageDraw.ImageDraw, suit: str, box, colour) -> None:
    """Draw one suit pip filling `box`. suit is S, H, D, C, or * for a joker."""
    x, y, w, h = box

    if suit == "H":
        dr.polygon(fit(heart_outline(), (x, y + 0.04 * h, w, 0.94 * h)), fill=colour)

    elif suit == "D":
        dr.polygon(fit([(0.5, 0.0), (0.93, 0.5), (0.5, 1.0), (0.07, 0.5)], box),
                   fill=colour)

    elif suit == "S":
        # An upside-down heart over a stem, which is how the pip is built.
        dr.polygon(fit(flip_y(heart_outline()), (x, y, w, 0.80 * h)), fill=colour)
        _stem(dr, box, colour)

    elif suit == "C":
        for cx, cy in ((0.5, 0.26), (0.24, 0.64), (0.76, 0.64)):
            dr.polygon(fit(circle(cx, cy, 0.24), (x, y, w, 0.84 * h)), fill=colour)
        _stem(dr, box, colour)

    elif suit == "*":
        dr.polygon(fit(star(), box), fill=colour)

    else:
        raise ValueError(f"unknown suit {suit!r}")


def _stem(dr: ImageDraw.ImageDraw, box, colour) -> None:
    """Flared stem shared by the spade and the club."""
    x, y, w, h = box
    dr.polygon(fit([(0.5, 0.46), (0.60, 0.78), (0.70, 0.99), (0.30, 0.99),
                    (0.40, 0.78)], (x, y, w, h)), fill=colour)


# ---------------------------------------------------------------------------
# Rank glyphs: stroke paths in the unit square, y down.
# ---------------------------------------------------------------------------
GLYPHS: dict[str, list[list[tuple[float, float]]]] = {
    "A": [[(0.02, 1.0), (0.5, 0.0), (0.98, 1.0)],
          [(0.19, 0.66), (0.81, 0.66)]],
    "1": [[(0.14, 0.26), (0.52, 0.02), (0.52, 1.0)]],
    "0": [arc(0.5, 0.5, 0.44, 0.49, 0, 360)],
    "2": [arc(0.5, 0.33, 0.44, 0.33, 180, 380) + [(0.03, 1.0), (0.97, 1.0)]],
    "3": [arc(0.5, 0.28, 0.40, 0.28, 165, 450),
          arc(0.5, 0.72, 0.44, 0.28, 270, 545)],
    "4": [[(0.74, 1.0), (0.74, 0.02)],
          [(0.74, 0.02), (0.04, 0.70), (0.97, 0.70)]],
    "5": [[(0.92, 0.03), (0.24, 0.03), (0.19, 0.40)],
          arc(0.5, 0.67, 0.43, 0.33, 285, 520)],
    "6": [[(0.86, 0.04), (0.50, 0.09), (0.21, 0.33), (0.09, 0.64)],
          arc(0.5, 0.64, 0.41, 0.36, 180, 540)],
    "7": [[(0.05, 0.04), (0.95, 0.04), (0.37, 1.0)]],
    "8": [arc(0.5, 0.24, 0.35, 0.24, 0, 360),
          arc(0.5, 0.72, 0.43, 0.28, 0, 360)],
    "9": [arc(0.5, 0.30, 0.40, 0.30, 0, 360),
          [(0.90, 0.30), (0.90, 0.68), (0.72, 0.94), (0.44, 1.0)]],
    "J": [[(0.78, 0.03), (0.78, 0.70)],
          arc(0.46, 0.70, 0.32, 0.30, 0, 180)],
    "Q": [arc(0.5, 0.5, 0.42, 0.48, 0, 360),
          [(0.60, 0.66), (0.98, 1.02)]],
    "K": [[(0.10, 0.0), (0.10, 1.0)],
          [(0.95, 0.0), (0.10, 0.54)],
          [(0.30, 0.44), (0.98, 1.0)]],
}


def draw_glyph(dr: ImageDraw.ImageDraw, ch: str, box, colour, weight: float) -> None:
    """Stroke one glyph into `box`. weight is the pen width in pixels."""
    w = max(1, int(round(weight)))
    r = w / 2.0
    for stroke in GLYPHS[ch]:
        pts = fit(stroke, box)
        dr.line(pts, fill=colour, width=w, joint="curve")
        # Round the caps; PIL's line() leaves them square.
        for px, py in (pts[0], pts[-1]):
            dr.ellipse((px - r, py - r, px + r, py + r), fill=colour)


def draw_rank(dr: ImageDraw.ImageDraw, rank: str, box, colour, weight: float) -> None:
    """Draw a rank, handling the ten's two glyphs."""
    if rank == "T":
        x, y, w, h = box
        gap = 0.10 * w
        gw = (w - gap) / 2.0
        draw_glyph(dr, "1", (x, y, gw, h), colour, weight)
        draw_glyph(dr, "0", (x + gw + gap, y, gw, h), colour, weight)
    else:
        draw_glyph(dr, rank, box, colour, weight)


# ---------------------------------------------------------------------------
# Card faces
# ---------------------------------------------------------------------------
def blank_card(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """White rounded face with a hairline edge, on transparency."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    radius = max(2, int(0.10 * w))
    inset = max(1, int(round(0.012 * w)))
    dr.rounded_rectangle((inset, inset, w - 1 - inset, h - 1 - inset),
                         radius=radius, fill=FACE, outline=EDGE,
                         width=max(1, int(round(0.016 * w))))
    return im, dr


def render_face(rank_char: str, suit_char: str, is_red: bool,
                w: int, h: int) -> Image.Image:
    """One card face at the requested pixel size."""
    W, H = w * SUPERSAMPLE, h * SUPERSAMPLE
    im, dr = blank_card(W, H)
    ink = RED if is_red else BLACK
    pen = 0.052 * W            # stroke weight for the corner rank
    pip = "*" if rank_char == "Z" else suit_char

    # --- corner index, drawn once then pasted twice, second copy rotated ---
    corner = Image.new("RGBA", (int(0.36 * W), int(0.40 * H)), (0, 0, 0, 0))
    cdr = ImageDraw.Draw(corner)
    cw, ch = corner.size
    if rank_char == "Z":
        # Joker: no rank letter, just the star, so it cannot read as a jack.
        draw_pip(cdr, "*", (0.08 * cw, 0.08 * ch, 0.80 * cw, 0.58 * ch), ink)
    else:
        rank_w = 0.92 * cw if rank_char == "T" else 0.60 * cw
        draw_rank(cdr, rank_char, (0.05 * cw, 0.02 * ch, rank_w, 0.48 * ch), ink, pen)
        draw_pip(cdr, pip, (0.12 * cw, 0.58 * ch, 0.40 * cw, 0.32 * ch), ink)

    ox, oy = int(0.07 * W), int(0.05 * H)
    im.alpha_composite(corner, (ox, oy))
    im.alpha_composite(corner.rotate(180), (W - cw - ox, H - ch - oy))

    # --- centre ----------------------------------------------------------
    if rank_char in ("J", "Q", "K"):
        # No court art survives 48x64, so the centre is a large rank letter
        # with its suit beneath it: readable, and unmistakably a face card.
        gw, gh = 0.26 * W, 0.28 * H
        draw_glyph(dr, rank_char, ((W - gw) / 2, 0.26 * H, gw, gh), ink, 0.072 * W)
        draw_pip(dr, pip, ((W - 0.24 * W) / 2, 0.60 * H, 0.24 * W, 0.19 * H), ink)
    else:
        size = 0.40 * H
        draw_pip(dr, pip, ((W - size) / 2, (H - size) / 2, size, size), ink)

    return im.resize((w, h), Image.LANCZOS)


def render_back(w: int, h: int) -> Image.Image:
    """Card back: a lattice over solid ink, inside the white face margin."""
    W, H = w * SUPERSAMPLE, h * SUPERSAMPLE
    im, _dr = blank_card(W, H)
    radius = max(2, int(0.10 * W))
    pad = int(0.08 * W)
    panel = (pad, pad, W - 1 - pad, H - 1 - pad)
    panel_radius = int(radius * 0.7)

    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    idr = ImageDraw.Draw(ink)
    idr.rounded_rectangle(panel, radius=panel_radius, fill=BACK_INK)
    step = int(0.16 * W)
    lw = max(1, int(0.014 * W))
    line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ldr = ImageDraw.Draw(line)
    for i in range(-H, W + H, step):
        ldr.line([(i, 0), (i + H, H)], fill=BACK_LINE, width=lw)
        ldr.line([(i, H), (i + H, 0)], fill=BACK_LINE, width=lw)

    # Clip the lattice to the ink panel, then stamp the panel onto the face.
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(panel, radius=panel_radius, fill=255)
    ink.paste(line, (0, 0), Image.composite(line.split()[3], mask.point(lambda v: 0), mask))
    im.alpha_composite(ink)
    return im.resize((w, h), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=48)
    ap.add_argument("--h", type=int, default=64)
    ap.add_argument("--out", default=str(ROOT / "build" / "cards"))
    ap.add_argument("--jokers", action="store_true")
    ap.add_argument("--sheet", help="also write a contact sheet here")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = deck(jokers=args.jokers)
    for r in rows:
        code = r["code"]
        render_face(code[0], code[1], r["red"], args.w, args.h).save(out / f"{code}.png")

    render_back(args.w, args.h).save(out / "BK.png")
    print(f"rendered {len(rows)} cards + back at {args.w}x{args.h} into {out}")

    if args.sheet:
        cols = 14
        pad = 4
        cells = [Image.open(out / f"{r['code']}.png") for r in rows]
        cells.append(Image.open(out / "BK.png"))
        n_rows = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (args.w + pad) + pad,
                                  n_rows * (args.h + pad) + pad), (60, 62, 70))
        for i, img in enumerate(cells):
            x = pad + (i % cols) * (args.w + pad)
            y = pad + (i // cols) * (args.h + pad)
            sheet.paste(img, (x, y), img)
        Path(args.sheet).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.sheet)
        print(f"wrote {args.sheet}")


if __name__ == "__main__":
    main()
