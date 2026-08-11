"""
Clone (or update) the upstream artwork repositories into vendor/.

    python tools/fetch_sources.py

Shallow clones only -- together they are a few hundred MB at full depth.

LICENSING
---------
flag-icons : MIT. Unrestricted for this use.
mapsicon   : NOT an OSI licence. The upstream README states, verbatim:
                 "Do what you want with them as long as you mention me in your
                  project. Please don't resell them - I forbid it!"
             Fine for a personal/hobby project WITH attribution to David Jaiss.
             NOT usable in anything you sell. See README.md for a public-domain
             alternative (Natural Earth) if that ever becomes a problem.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"

SOURCES = [
    ("flag-icons", "https://github.com/lipis/flag-icons.git", "MIT"),
    ("mapsicon", "https://github.com/djaiss/mapsicon.git", "attribution-only, no resale"),
]


def main() -> None:
    if shutil.which("git") is None:
        sys.exit("git not found on PATH.")

    VENDOR.mkdir(exist_ok=True)
    for name, url, lic in SOURCES:
        dest = VENDOR / name
        if dest.is_dir():
            print(f"[{name}] already present, pulling latest ({lic})")
            subprocess.run(["git", "pull", "--depth", "1"], cwd=dest, check=False)
        else:
            print(f"[{name}] cloning {url} ({lic})")
            subprocess.run(
                ["git", "clone", "--depth", "1", url, str(dest)], check=True
            )

    print("\nSources ready. Next: python tools/build.py")
    print("\nREMINDER: mapsicon requires attribution to David Jaiss and forbids")
    print("resale. Keep the credit in the generated headers and your game's")
    print("about screen.")


if __name__ == "__main__":
    main()
