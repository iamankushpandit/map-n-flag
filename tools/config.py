"""
Tunable configuration for the CountryAssets pipeline.

Change a value here, re-run `python tools/build.py`, and the whole generated
C++ library under lib/CountryAssets/ is rebuilt to match.
"""

# ---------------------------------------------------------------------------
# Which countries to generate
# ---------------------------------------------------------------------------
# "un195"   : 193 UN member states + Holy See + Palestine        (default)
# "all"     : every ISO 3166-1 alpha-2 code that has assets      (~249)
# "curated" : a hand-picked set of highly recognisable countries (~60)
SCOPE = "un195"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
# 80x60 is the measured sweet spot: US stripes resolve without moire (they
# alias badly at 64x48), and India's chakra / Korea's trigrams survive.
# Going to 96x72 costs +43% flash and buys almost nothing, because the
# emblem-heavy flags (MX, PT, EC) are unreadable at every size in this range.
# Source art is 4:3, so 4:3 output means no non-uniform stretching.
FLAG_W = 80
FLAG_H = 60

# ---------------------------------------------------------------------------
# Map outlines
# ---------------------------------------------------------------------------
# Each silhouette is cropped to its tight bounding box, then scaled to fit
# inside a MAP_BOX x MAP_BOX square with aspect preserved. Cropping matters a
# lot: Chile becomes ~17x96 instead of a mostly-empty 96x96.
MAP_BOX = 96

# Ink colour for map silhouettes, as (R, G, B). The 16-entry palette is an
# alpha ramp of this single colour, which gives antialiased edges identical to
# a 4-bit alpha mask while staying in a format both LVGL v8 and v9 can render.
MAP_INK = (0x1E, 0x3A, 0x8A)

# Drop tiny disconnected specks (stray islands) below this fraction of the
# country's total ink. Keeps small nations legible; set to 0.0 to disable.
MAP_SPECK_THRESHOLD = 0.0

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
# Number of .cpp files to spread the byte arrays across. More files = smaller
# translation units = faster/less memory-hungry compiles.
TU_SPLIT = 4

# Emit descriptors that compile against both LVGL v8 and v9.
# (The pixel byte layout is identical between the two; only the descriptor
# struct differs, so this costs zero extra flash.)
DUAL_VERSION = True

# Bytes per line in the generated C arrays.
BYTES_PER_LINE = 16
