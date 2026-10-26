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
# Map outlines (US states only)
# ---------------------------------------------------------------------------
# Each silhouette is cropped to its tight bounding box, then scaled to fit
# inside a MAP_BOX x MAP_BOX square with aspect preserved. Cropping matters a
# lot: Chile becomes ~17x96 instead of a mostly-empty 96x96.
MAP_BOX = 96

# Ink colour for map silhouettes (used for US state outlines), as (R, G, B).
# The 16-entry palette is an alpha ramp of this single colour, which gives
# antialiased edges identical to a 4-bit alpha mask while staying in a format
# both LVGL v8 and v9 can render.
MAP_INK = (0x1E, 0x3A, 0x8A)

# Drop tiny disconnected specks (stray islands) below this fraction of the
# state's total ink. Keeps small states legible; set to 0.0 to disable.
MAP_SPECK_THRESHOLD = 0.0

# ---------------------------------------------------------------------------
# US States
# ---------------------------------------------------------------------------
# Set True to generate US state flags and map outlines alongside the country
# data. Both sources are commercially safe:
#   Flags  : fonttools/region-flags (public domain, Wikipedia-sourced)
#   Maps   : Natural Earth admin_1  (public domain)
#
# Uses a parallel API: mnf_state_flag("CA"), mnf_state_map("CA"), etc.
# State codes are 2-letter USPS abbreviations, not ISO 3166-2 "US-CA".
GENERATE_STATES = True

# Set False to omit state outline maps. The state outlines come from
# Natural Earth (public domain), so there is no commercial restriction.
GENERATE_STATE_MAPS = True

# ---------------------------------------------------------------------------
# Playing cards
# ---------------------------------------------------------------------------
# Set True to generate a standard 52-card deck plus a card back. The artwork
# is drawn from vector primitives by tools/render_cards.py -- no upstream SVGs,
# no font, and therefore nothing to attribute or license.
#
# Uses a parallel API: mnf_card("AS"), mnf_card_back(), etc. A card code is
# rank then suit: ranks A 2-9 T J Q K, suits S H D C ("TD" is the ten of
# diamonds).
GENERATE_CARDS = True

# 48x64 is a 0.75 aspect, close to a real 2.5x3.5" card, and costs 1,600 B per
# card -- a full deck plus back is ~83 KiB. Corner ranks stop being readable
# below about 40x56; above 64x88 you are paying flash for very little.
CARD_W = 48
CARD_H = 64

# Add the two jokers ("ZR" red, "ZB" black). Off by default: most games do not
# need them, and each one is another 1,600 B.
CARD_JOKERS = False

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
