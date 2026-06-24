#!/usr/bin/env python3
"""Optionally fetch upstream reference docs into resources/downloaded/ (git-ignored).

The packaged `.md` notes in src/printforge/resources are what get injected into
prompts. This script just pulls full upstream copies for human reference. We only
fetch openly-licensed pages and never vendor them into the repo.

Usage:
    python scripts/fetch_resources.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

# (filename, url) -- openly accessible reference pages.
DOCS: list[tuple[str, str]] = [
    ("build123d_cheat_sheet.html", "https://build123d.readthedocs.io/en/latest/cheat_sheet.html"),
    ("build123d_api.html", "https://build123d.readthedocs.io/en/latest/direct_api_reference.html"),
    ("iso10303_step.html", "https://en.wikipedia.org/wiki/ISO_10303"),
    ("stl_format.html", "https://en.wikipedia.org/wiki/STL_(file_format)"),
    ("staunton_chess_set.html", "https://en.wikipedia.org/wiki/Staunton_chess_set"),
    ("elgin_marbles.html", "https://en.wikipedia.org/wiki/Elgin_Marbles"),
]

OUT = Path(__file__).resolve().parents[1] / "src" / "printforge" / "resources" / "downloaded"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name, url in DOCS:
        dest = OUT / name
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "printforge-fetch/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                dest.write_bytes(resp.read())
            print(f"  ok   {name}")
        except Exception as e:  # network is best-effort
            failures += 1
            print(f"  FAIL {name}: {e}")
    print(f"\nSaved to {OUT} ({len(DOCS) - failures}/{len(DOCS)} ok)")
    return 1 if failures == len(DOCS) else 0


if __name__ == "__main__":
    sys.exit(main())
