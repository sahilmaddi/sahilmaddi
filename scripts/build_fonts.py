"""Subset the fonts the cards embed (printable ASCII + a few arrows) and write
fonts/*.woff plus fonts/metrics.json, so the SVGs carry their own fonts.

    python scripts/build_fonts.py fonts

Needs fonttools. The Action runs this once, when fonts/ doesn't exist yet,
after installing Ubuntu's fonts-inter and fonts-dejavu-core packages.
Your site uses JetBrains Mono: point "mono-400.woff" at JetBrainsMono-Regular.ttf
instead if you want it, then delete fonts/ so the Action rebuilds them.
"""
import json
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "fonts"
os.makedirs(OUT, exist_ok=True)
CHARS = "".join(chr(c) for c in range(0x20, 0x7F)) + "·—–’‘“”→↗↑…•"

JOBS = [
    ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "sans-400.woff"),
    ("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "sans-600.woff"),
    ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "sans-700.woff"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "mono-400.woff"),
]

metrics = {}
for src, name in JOBS:
    font = TTFont(src)
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern", "liga", "calt", "tnum", "lnum"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=CHARS)
    sub.subset(font)
    font.flavor = "woff"
    path = os.path.join(OUT, name)
    font.save(path)
    # Check the name table: a file called "Regular" can turn out to be the italic.
    names = font["name"]
    print(f"{name:16s} {os.path.getsize(path) / 1024:5.1f} KB  "
          f"{names.getDebugName(4)!r}  weight {font['OS/2'].usWeightClass}")
    # Advance widths, so the renderer can measure text without fontTools.
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    metrics[name] = {"upm": font["head"].unitsPerEm,
                     "adv": {chr(c): hmtx[g][0] for c, g in cmap.items() if chr(c) in CHARS}}

with open(os.path.join(OUT, "metrics.json"), "w") as f:
    json.dump(metrics, f, separators=(",", ":"))
print("metrics.json written")
