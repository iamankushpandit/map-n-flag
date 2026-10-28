"""
Clone (or update) the upstream artwork repositories into vendor/.

    python tools/fetch_sources.py

Shallow clones only -- together they are a few hundred MB at full depth.

LICENSING
---------
flag-icons   : MIT. Unrestricted for this use.
region-flags : Public domain (Wikipedia-sourced). US state flags.
Natural Earth: Public domain. US state outlines.
asl-wpclipart: Public domain / CC0 (WPClipart via Wikimedia Commons). ASL hands.
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"

GIT_SOURCES = [
    ("flag-icons", "https://github.com/lipis/flag-icons.git", "MIT"),
    ("region-flags", "https://github.com/fonttools/region-flags.git", "public domain"),
]

NE_GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_10m_admin_1_states_provinces.geojson"
)
NE_DEST = VENDOR / "natural-earth" / "ne_10m_admin_1_states_provinces.geojson"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
SIGN_DEST = VENDOR / "asl-wpclipart"
# Commons asks automated clients to identify themselves, and answers an
# anonymous burst with a short error page instead of the file -- which is why
# every download below is checked against the size Commons itself reports.
USER_AGENT = "map-n-flag-fetch/1.0 (https://github.com/iamankushpandit/map-n-flag)"


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


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_asl_signs() -> None:
    """Download the 26 ASL fingerspelling hands from Wikimedia Commons."""
    sys.path.insert(0, str(Path(__file__).parent))
    from signs_data import SIGNS, commons_title

    SIGN_DEST.mkdir(parents=True, exist_ok=True)
    titles = "|".join(commons_title(letter) for letter, _ in SIGNS)
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "url|size", "titles": titles,
    })
    pages = json.loads(_get(f"{COMMONS_API}?{query}"))["query"]["pages"]

    fetched = 0
    for page in pages.values():
        info = (page.get("imageinfo") or [None])[0]
        if info is None:
            sys.exit(f"[asl-wpclipart] Commons has no file {page['title']}")
        # Commons answers with spaces where the request had underscores:
        # "File:Sign language A.svg". The letter is the last one before ".svg".
        letter = page["title"][-5].lower()
        dest = SIGN_DEST / f"{letter}.svg"
        if dest.exists() and dest.stat().st_size == info["size"]:
            continue
        url = info["url"].split("?")[0]
        for attempt in range(6):
            data = _get(url)
            if len(data) == info["size"]:
                dest.write_bytes(data)
                fetched += 1
                break
            time.sleep(2 + attempt * 2)
        else:
            sys.exit(f"[asl-wpclipart] {letter}.svg: got {len(data)} bytes, "
                     f"Commons says {info['size']} -- rate limited, try again")
        time.sleep(0.5)
    print(f"[asl-wpclipart] {len(pages)} hands present, {fetched} downloaded "
          "(public domain / CC0)")


def main() -> None:
    if shutil.which("git") is None:
        sys.exit("git not found on PATH.")

    VENDOR.mkdir(exist_ok=True)
    for name, url, lic in GIT_SOURCES:
        fetch_git(name, url, lic)
    fetch_natural_earth()
    fetch_asl_signs()

    print("\nSources ready. Next: python tools/build.py")


if __name__ == "__main__":
    main()
