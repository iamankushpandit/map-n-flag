"""
Clone (or update) the upstream artwork repositories into vendor/.

    python tools/fetch_sources.py

Shallow clones only -- together they are a few hundred MB at full depth.

LICENSING
---------
flag-icons   : MIT. Unrestricted for this use.
mapsicon     : NOT an OSI licence. The upstream README states, verbatim:
                   "Do what you want with them as long as you mention me in your
                    project. Please don't resell them - I forbid it!"
               Fine for a personal/hobby project WITH attribution to David Jaiss.
               NOT usable in anything you sell. See README.md for a public-domain
               alternative (Natural Earth) if that ever becomes a problem.
region-flags : Public domain (Wikipedia-sourced). US state flags.
Natural Earth: Public domain. US state outlines.
"""
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"

GIT_SOURCES = [
    ("flag-icons", "https://github.com/lipis/flag-icons.git", "MIT"),
    ("mapsicon", "https://github.com/djaiss/mapsicon.git", "attribution-only, no resale"),
    ("region-flags", "https://github.com/fonttools/region-flags.git", "public domain"),
]

NE_GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_admin_1_states_provinces.geojson"
)
NE_DEST = VENDOR / "natural-earth" / "ne_10m_admin_1_states_provinces.geojson"


def fetch_git(name: str, url: str, lic: str) -> None:
    dest = VENDOR / name
    if dest.is_dir():
        print(f"[{name}] already present, pulling latest ({lic})")
        subprocess.run(["git", "pull", "--depth", "1"], cwd=dest, check=False)
    else:
        print(f"[{name}] cloning {url} ({lic})")
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)], check=True
        )


def fetch_natural_earth() -> None:
    if NE_DEST.exists():
        print(f"[natural-earth] already present: {NE_DEST.name}")
        return
    NE_DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"[natural-earth] downloading {NE_DEST.name} (public domain) ...")
    urllib.request.urlretrieve(NE_GEOJSON_URL, NE_DEST)
    size_mb = NE_DEST.stat().st_size / 1048576
    print(f"[natural-earth] saved {size_mb:.1f} MiB")


def main() -> None:
    if shutil.which("git") is None:
        sys.exit("git not found on PATH.")

    VENDOR.mkdir(exist_ok=True)
    for name, url, lic in GIT_SOURCES:
        fetch_git(name, url, lic)
    fetch_natural_earth()

    print("\nSources ready. Next: python tools/build.py")
    print("\nREMINDER: mapsicon requires attribution to David Jaiss and forbids")
    print("resale. Keep the credit in the generated headers and your game's")
    print("about screen.")


if __name__ == "__main__":
    main()
