"""One QR code per printed URL, and then read every one of them back.

    python tools/verify_printed_urls.py     # must be clean first
    python tools/generate_qr_codes.py

A QR code encoding a dead URL is worse than no QR code at all. A reader can
look at a printed address and judge it before typing; they cannot look at a
QR code and judge anything. They point a camera at a black square on faith,
and whatever comes back is what the book told them to go to. So this refuses
to generate a code for any URL that the verification tool did not mark OK in
its most recent run, and it reads that run's JSON rather than checking again,
so the codes and the verification cannot disagree about what was live.

## Every code is decoded and compared, and not by the encoder

After writing each PNG it is read back with zxing-cpp, a decoder that shares
no code with the encoder, and the decoded string is compared against the URL
it was generated from. Decoding with the encoding library would establish that
qrcode agrees with itself. The question is whether a scanner that has never
heard of qrcode gets the right URL back.

This is the same discipline as proving the certificate check bites, and it is
the last opportunity to catch an error before it reaches paper. After that the
only fix is a reprint.

## Print settings

Error correction level H, the highest, which can restore up to about thirty
per cent of the symbol's codewords. These go on paper that gets folded, spilled
on, photocopied and read in bad light, and the margin is cheap: it costs a
denser symbol, and the symbol is printed at a fixed size anyway.

"Thirty per cent damage" is the usual way that is stated and it is not what a
typesetter would measure, so these codes were damaged deliberately to find out.
On this set, a contiguous blot covering up to twenty per cent of the symbol
still decoded, and twenty-three per cent did not. Two things are much worse
than that headline suggests. Damage to the three finder squares or the
alignment pattern is fatal at any size, because a scanner locates the symbol
before it corrects anything. And scattered speckle is far worse than one blot
of the same total area, because a single wrong module ruins the whole
eight-module codeword it sits in, so ten per cent of modules randomised was
already unreadable.

A quiet zone of four modules, which is the specified minimum. The quiet zone
is not decoration and is the most common thing lost when somebody crops a code
to fit a layout: without it many scanners will not see the symbol at all.

Minimum printed size is about 2 cm square. Below that, phone cameras struggle
at arm's length, which is the distance somebody actually holds a book at.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import qrcode
import zxingcpp
from PIL import Image
from qrcode.constants import ERROR_CORRECT_H

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFIED = REPO_ROOT / "printed_urls_report.json"
OUT = REPO_ROOT / "qr"

SITE = "https://lab.nexagenlabs.com"

# Four modules is the specified minimum quiet zone. Anything less and scanners
# start failing on codes that look perfectly fine to a person.
QUIET_ZONE_MODULES = 4

# Pixels per module. Ten keeps a typical code comfortably above 300 dpi at the
# 2 cm minimum printed size, so the printer rather than the file is the limit.
BOX_SIZE = 10

MINIMUM_PRINTED_SIZE_CM = 2.0

# The file name for each printed path. Named for the chapter rather than
# numbered in sequence, so a layout cannot silently pair ch07's code with
# ch08's caption. That mistake is invisible on the page and fatal to the
# reader.
FILENAMES = {
    "/": "hub",
    "/setup": "setup",
    "/references": "references",
}


def filename_for(path: str) -> str:
    if path in FILENAMES:
        return FILENAMES[path]
    return path.lstrip("/")


@dataclass
class Generated:
    path: str
    url: str
    filename: str
    modules: int
    version: int
    decoded: str | None
    matches: bool
    note: str


def printed_paths() -> tuple[str, ...]:
    """The thirteen the book prints, from the test that pins them."""
    spec = importlib.util.spec_from_file_location(
        "_site_urls", REPO_ROOT / "tests" / "test_site_urls.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.PRINTED_PATHS)


def verified_urls() -> dict[str, str]:
    """Printed paths the verification tool marked OK, mapped to their URL.

    Two filters, and the second exists because the first is not enough.

    Read from that tool's output rather than checked again here: two tools
    making their own network requests would eventually disagree, and the one
    that disagreed quietly would be this one, because nobody reads a
    generator's output the way they read a verification report.

    Then intersected with the printed contract, because OK does not mean
    "print this". After /ch01 and /ch02 were changed to assert that they
    correctly return 404 rather than that they reach the hub, they began
    reporting OK, and a first version of this file duly generated ch01.png and
    ch02.png. The book prints thirteen URLs. A fourteenth code in the folder is
    an invitation to place it, and the place it would go is beside a chapter
    whose address deliberately does not resolve.
    """
    if not VERIFIED.exists():
        raise SystemExit(
            f"{VERIFIED.name} is not present. Run tools/verify_printed_urls.py "
            "first: no code is generated for a URL nobody has confirmed is "
            "live."
        )
    results = json.loads(VERIFIED.read_text(encoding="utf-8"))
    ok = {r["path"]: r["requested"] for r in results if r["status"] == "OK"}

    printed = printed_paths()
    missing = [path for path in printed if path not in ok]
    if missing:
        raise SystemExit(
            f"These printed URLs are not marked OK in {VERIFIED.name}: "
            f"{missing}. Fix the site, re-run the verification tool, and only "
            "then generate codes. A QR code encoding a dead URL is worse than "
            "no QR code, because a reader can judge a printed address before "
            "typing it and cannot judge a black square before scanning it."
        )
    return {path: ok[path] for path in printed}


def generate(path: str, url: str) -> Generated:
    code = qrcode.QRCode(
        version=None,                     # smallest that fits the data
        error_correction=ERROR_CORRECT_H,
        box_size=BOX_SIZE,
        border=QUIET_ZONE_MODULES,
    )
    code.add_data(url)
    code.make(fit=True)

    name = filename_for(path)
    target = OUT / f"{name}.png"
    image = code.make_image(fill_color="black", back_color="white")
    image.save(target)

    # Read it back with a different library. Not the one that wrote it.
    decoded = zxingcpp.read_barcode(Image.open(target))
    text = decoded.text if decoded else None
    matches = text == url

    return Generated(
        path=path, url=url, filename=target.name,
        modules=code.modules_count, version=code.version,
        decoded=text, matches=matches,
        note=("decodes to the URL it was generated from" if matches
              else f"DECODED MISMATCH: got {text!r}"),
    )


def main() -> int:
    urls = verified_urls()
    if not urls:
        raise SystemExit(
            "No URL in the verification report is marked OK, so there is "
            "nothing safe to encode."
        )

    OUT.mkdir(exist_ok=True)
    generated = [generate(path, url) for path, url in sorted(urls.items())]

    lines = ["# QR codes for the printed URLs", ""]
    lines.append(f"{len(generated)} codes, error correction level H, quiet "
                 f"zone {QUIET_ZONE_MODULES} modules.")
    lines.append("")
    lines.append(f"**Minimum printed size {MINIMUM_PRINTED_SIZE_CM} cm "
                 "square.** Below that, phone cameras struggle at arm's "
                 "length, which is the distance somebody holds a book at.")
    lines.append("")
    lines.append("Only the thirteen addresses the book prints get a code. "
                 "There is deliberately no ch01 or ch02: those chapters ship "
                 "no code and the book prints no address for them.")
    lines.append("")
    lines.append("Every code below was decoded with zxing-cpp, which shares no "
                 "code with the encoder, and compared against the URL it was "
                 "generated from.")
    lines.append("")
    lines.append("| File | Encodes | Decoded back to | Version | Modules | Match |")
    lines.append("|---|---|---|---|---|---|")
    for item in generated:
        mark = "yes" if item.matches else "**NO**"
        lines.append(
            f"| `qr/{item.filename}` | {item.url} | {item.decoded} | "
            f"{item.version} | {item.modules} x {item.modules} | {mark} |"
        )
    lines.append("")

    bad = [item for item in generated if not item.matches]
    if bad:
        lines.append("## Mismatches, which must not reach paper")
        lines.append("")
        for item in bad:
            lines.append(f"**{item.filename}**: {item.note}")
        lines.append("")

    report = "\n".join(lines)
    (OUT / "README.md").write_text(report + QR_README_TAIL, encoding="utf-8",
                                   newline="\n")
    print(report)

    if bad:
        print(f"{len(bad)} code(s) did not decode to their own URL. "
              "Nothing goes to paper until this is clean.")
        return 1
    print(f"All {len(generated)} codes decode to the URL they encode.")
    return 0


QR_README_TAIL = """

## Regenerating

```
python tools/verify_printed_urls.py    # must exit 0
python tools/generate_qr_codes.py
```

The generator refuses to encode any URL the verification tool did not mark OK
in its most recent run. A QR code encoding a dead URL is worse than no QR code,
because a reader can judge a printed address before typing it and cannot judge
a black square before scanning it.

## For the typesetter

- **Do not crop the white margin.** It is a four-module quiet zone and it is
  part of the symbol, not padding. Many scanners will not see a code without
  it.
- **Do not print below 2 cm square.** Phone cameras struggle at arm's length
  below that, which is how far away a book is held.
- **Do not recolour, screen back, or place on a texture or photograph.** Level
  H tolerates damage, not low contrast. Black on white, full strength.
- **Nothing may overlap the three corner squares.** A logo or a caption over
  one is fatal at any size, because a scanner has to find the symbol before
  error correction does anything at all.
- Files are named for their chapter, so `ch07.png` belongs beside the Chapter 7
  address and nowhere else. There is no `ch01.png` or `ch02.png`, because those
  chapters ship no code and the book prints no address for them.

## How much damage these actually survive

Level H is specified to restore about thirty per cent of a symbol's codewords.
That is not a number a typesetter can act on, so these codes were damaged on
purpose to find one that is:

| Damage | Result |
|---|---|
| Contiguous blot over 20% of the symbol, clear of the corners | decodes |
| Contiguous blot over 23% | fails |
| Any blot across a corner square or the alignment pattern | fails at any size |
| 10% of modules randomised, scattered | fails |

Scattered speckle is much worse than one blot of the same area, because a
single wrong module ruins the entire eight-module codeword it sits in. Treat
the margin as insurance against a fold or a coffee ring in one place, not
against a bad print run everywhere.
"""


if __name__ == "__main__":
    sys.exit(main())
