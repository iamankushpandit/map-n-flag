"""
Render US state outlines from Natural Earth GeoJSON to individual PNGs.

    python tools/render_state_maps.py [--box 96] [--out build/state_maps]

Reads ne_10m_admin_1_states_provinces.geojson from vendor/natural-earth/,
extracts US state polygons, and renders each as a white-on-transparent PNG
suitable for the alpha_ramp_indexed pipeline in build.py.

No dependencies beyond Pillow -- GeoJSON is parsed directly.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GEOJSON_PATH = ROOT / "vendor" / "natural-earth" / "ne_10m_admin_1_states_provinces.geojson"

RENDER_SIZE = 2048


def extract_us_states(geojson: dict) -> dict[str, dict]:
    """Return {state_abbr: feature} for US states."""
    states = {}
    for feat in geojson["features"]:
        props = feat.get("properties", {})
        iso = props.get("iso_3166_2", "")
        if not iso.startswith("US-"):
            continue
        abbr = iso[3:]
        if len(abbr) != 2:
            continue
        states[abbr] = feat
    return states


def collect_coords(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    """Normalise Polygon/MultiPolygon to list of polygons.

    Each polygon is [exterior_ring, hole1, hole2, ...].
    Each ring is [(lon, lat), ...].
    """
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        return [coords]
    elif gtype == "MultiPolygon":
        return coords
    return []


def _wrap_longitude(polygons: list) -> list:
    """Shift longitudes so antimeridian-crossing shapes stay contiguous.

    If both hemispheres are present (e.g. Alaska's Aleutians), shift
    negative longitudes by +360 so everything lies on a continuous range.
    """
    has_neg = any(lon < 0 for poly in polygons for ring in poly for lon, _ in ring)
    has_pos = any(lon > 0 for poly in polygons for ring in poly for lon, _ in ring)
    span = (max(lon for poly in polygons for ring in poly for lon, _ in ring) -
            min(lon for poly in polygons for ring in poly for lon, _ in ring))
    if has_neg and has_pos and span > 180:
        return [
            [[(lon + 360 if lon < 0 else lon, lat) for lon, lat in ring]
             for ring in poly]
            for poly in polygons
        ]
    return polygons


def render_state(feature: dict, box: int) -> Image.Image | None:
    """Render a state outline as a grayscale alpha image, cropped and scaled."""
    polygons = collect_coords(feature["geometry"])
    if not polygons:
        return None

    polygons = _wrap_longitude(polygons)

    all_lons, all_lats = [], []
    for poly in polygons:
        for ring in poly:
            for lon, lat in ring:
                all_lons.append(lon)
                all_lats.append(lat)

    if not all_lons:
        return None

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    # Latitude correction: scale x by cos(center_lat) for less distortion.
    center_lat = (min_lat + max_lat) / 2.0
    cos_lat = math.cos(math.radians(center_lat))

    lon_span = (max_lon - min_lon) * cos_lat
    lat_span = max_lat - min_lat
    if lon_span <= 0 or lat_span <= 0:
        return None

    # Render at high resolution, then downsample for antialiasing.
    scale = RENDER_SIZE / max(lon_span, lat_span)

    def project(lon: float, lat: float) -> tuple[float, float]:
        x = (lon - min_lon) * cos_lat * scale
        y = (max_lat - lat) * scale
        return (x, y)

    w_hi = max(1, int(math.ceil(lon_span * scale)))
    h_hi = max(1, int(math.ceil(lat_span * scale)))

    img = Image.new("L", (w_hi, h_hi), 0)
    draw = ImageDraw.Draw(img)

    for poly in polygons:
        if not poly:
            continue
        # Exterior ring (filled white).
        ext = [project(lon, lat) for lon, lat in poly[0]]
        if len(ext) >= 3:
            draw.polygon(ext, fill=255)
        # Interior rings / holes (filled black to cut them out).
        for hole in poly[1:]:
            h_pts = [project(lon, lat) for lon, lat in hole]
            if len(h_pts) >= 3:
                draw.polygon(h_pts, fill=0)

    # Crop to tight bounding box.
    bbox = img.getbbox()
    if bbox is None:
        return None
    img = img.crop(bbox)

    # Scale to fit within box x box, preserving aspect.
    scale_f = min(box / img.width, box / img.height)
    w_out = max(1, round(img.width * scale_f))
    h_out = max(1, round(img.height * scale_f))
    img = img.resize((w_out, h_out), Image.LANCZOS)

    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", type=int, default=96,
                    help="Max dimension of output silhouettes (default 96)")
    ap.add_argument("--out", type=str, default=str(ROOT / "build" / "state_maps"),
                    help="Output directory for PNGs")
    args = ap.parse_args()

    if not GEOJSON_PATH.exists():
        sys.exit(f"Missing {GEOJSON_PATH}. Run: python tools/fetch_sources.py")

    print(f"loading {GEOJSON_PATH.name} ...")
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    states = extract_us_states(geojson)
    print(f"found {len(states)} US states/territories")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    missing = []
    for abbr in sorted(states):
        img = render_state(states[abbr], args.box)
        if img is None:
            missing.append(abbr)
            continue
        img.save(out_dir / f"{abbr}.png")
        rendered += 1

    print(f"rendered {rendered} state outlines to {out_dir}")
    if missing:
        print(f"  failed to render: {', '.join(missing)}")


if __name__ == "__main__":
    main()
