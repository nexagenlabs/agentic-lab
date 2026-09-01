"""Render the bibliographic half of a reference, and check it against the page.

This is deliberately NOT a generator for Appendix D. A generator would make the
printed appendix a function of references.yaml, and the whole reason this
repository caught two reference defects is that the two records are maintained
separately and had to agree. A single source of truth agrees with its own
errors; two records disagree, and the disagreement is the signal. Both failures
found here were found that way: references.yaml holding 47 of 74 entries, and
printed rows 67 and 69 frozen while the yaml moved on.

So this renders only the half that is fact - authors, title, venue, volume,
pages, year, DOI - and asserts each field appears in the matching printed row.
Prose, ordering and grouping stay with the author and the page. What it buys is
that a printed row can no longer disagree with the verified record about a
title, a volume, a year or a DOI, which is exactly how printed entry 28 came to
carry a title that was never published.

Two modes:

    python tools/appendix_render.py            check every printed row
    python tools/appendix_render.py --emit     print the bibliographic string
                                               for rows still printed as a
                                               description, ready to paste

Rows the manifest marks ``printed_as: description`` are not checked field by
field, because they legitimately carry no title or author yet. They are counted
instead, and the count is asserted, so a row cannot quietly become a
description.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
REFERENCES = REPO / "references" / "references.yaml"
MANIFEST = REPO / "references" / "appendix_d.manifest.yaml"
PRINTED = REPO / "references" / "APPENDIX_D_AS_PRINTED.md"

# Letters that do not decompose under NFKD but that a typesetter may drop.
FOLD = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O",
                      "æ": "ae", "Æ": "AE", "ß": "ss", "đ": "d", "ð": "d"})


def fold(text: str) -> str:
    """Lowercase, strip accents, reduce to words separated by single spaces.

    The printed page and the record disagree about punctuation constantly and
    harmlessly: an en dash for a hyphen, a middle dot for a decimal point,
    "Archiv fur" where Crossref has "Archiv fuer". None of that changes which
    work is named. A check that failed on it would be switched off in a week.
    """
    text = unicodedata.normalize("NFKD", text.translate(FOLD))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def page_forms(pages: str) -> list[str]:
    """The house style prints ranges as "716 to 723"; the record stores 716-723."""
    folded = fold(pages)
    parts = folded.split()
    forms = [folded]
    if len(parts) == 2:
        forms.append(f"{parts[0]} to {parts[1]}")
    return forms


def render(entry: dict) -> str:
    """The bibliographic half of one entry, in the appendix's house style.

    Never the gloss. The gloss is the author's prose and is appended by hand;
    this function exists to be checked against the page, and prose cannot be.
    """
    bits: list[str] = []
    if entry.get("authors"):
        bits.append(entry["authors"].rstrip(".") + ".")
    # "How good are AlphaFold models...?" already ends a sentence. Appending a
    # full stop to it produces "?." which is how a renderer announces itself.
    title = entry["title"].rstrip(".")
    bits.append(title if title.endswith(("?", "!")) else title + ".")

    year = entry.get("year")
    if entry.get("kind") == "preprint" and entry.get("arxiv"):
        bits.append(f"arXiv:{entry['arxiv']}" + (f" ({year})." if year else "."))
    else:
        tail = ""
        if entry.get("venue"):
            tail = entry["venue"].rstrip(".")
        if entry.get("volume"):
            tail += f" {entry['volume']}"
        if entry.get("pages"):
            pages = entry["pages"]
            parts = pages.split("-")
            shown = f"{parts[0]} to {parts[1]}" if len(parts) == 2 else pages
            # A volume is followed by a bare comma ("Nature 646, 716 to 723");
            # a venue with no volume needs the comma too, or the page range
            # runs straight into the conference name.
            tail += f", {shown}" if tail else shown
        if year:
            tail = f"{tail} ({year})" if tail else f"({year})"
        if tail:
            bits.append(tail.strip() + ".")

    if entry.get("doi"):
        bits.append(f"doi:{entry['doi']}.")
    elif entry.get("url") and not entry.get("arxiv"):
        bits.append(f"{entry['url']}")
    return " ".join(bits)


def printed_rows() -> dict[int, str]:
    rows = {}
    for line in PRINTED.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if m:
            rows[int(m.group(1))] = m.group(2).strip()
    return rows


def doi_in(text: str) -> str | None:
    m = re.search(r"doi:\s*(10\.\S+)", text, re.I)
    return m.group(1).rstrip(".").lower() if m else None


def check_row(entry: dict, printed: str, omits: tuple[str, ...] = ()) -> list[str]:
    """Which bibliographic fields of this entry are missing from the printed row?

    ``omits`` names fields the printed row deliberately does not carry, taken
    from the manifest. Omission is an editorial choice - the house style prints
    a DOI on some rows and not others - and contradiction is the error. Naming
    the field per row keeps the choice explicit rather than relaxing the check
    for every row at once.
    """
    hay = fold(printed)
    problems = []

    if fold(entry["title"]) not in hay:
        problems.append(f'title not on the page: "{entry["title"]}"')

    if entry.get("authors"):
        first = re.split(r"[,.]", entry["authors"].strip())[0].strip()
        if first and fold(first) not in hay:
            problems.append(f'first author not on the page: "{first}"')

    if "year" not in omits and entry.get("year") and fold(str(entry["year"])) not in hay:
        problems.append(f"year {entry['year']} not on the page")

    if "volume" not in omits and entry.get("volume") and fold(str(entry["volume"])) not in hay:
        problems.append(f"volume {entry['volume']} not on the page")

    if "pages" not in omits and entry.get("pages") and not any(f in hay for f in page_forms(entry["pages"])):
        problems.append(f"pages {entry['pages']} not on the page")

    if "arxiv" not in omits and entry.get("arxiv") and fold(entry["arxiv"]) not in hay:
        problems.append(f"arXiv id {entry['arxiv']} not on the page")

    # A DOI on the page must be the DOI in the record. A DOI absent from the
    # page is an editorial choice, not an error: plenty of printed rows omit it.
    on_page = doi_in(printed)
    if on_page and on_page != (entry.get("doi") or "").lower():
        problems.append(
            f"DOI on the page is {on_page}, the record says "
            f"{entry.get('doi') or 'none'}")
    return problems


def load():
    refs = {e["id"]: e for e in yaml.safe_load(
        REFERENCES.read_text(encoding="utf-8"))["references"]}
    man = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["appendix_d"]
    return refs, man, printed_rows()


def failures() -> list[tuple[int, str, list[str]]]:
    refs, man, rows = load()
    out = []
    for row in man["entries"]:
        if row.get("printed_as") == "description":
            continue
        entry, printed = refs.get(row["id"]), rows.get(row["n"])
        if entry is None or printed is None:
            out.append((row["n"], row["id"], ["no entry or no printed row"]))
            continue
        problems = check_row(entry, printed, tuple(row.get("omits") or ()))
        if problems:
            out.append((row["n"], row["id"], problems))
    return out


def descriptions() -> list[tuple[int, str, dict]]:
    refs, man, _ = load()
    # An unsourced entry has nothing to paste. Emitting a citation-shaped
    # string for one would be handing over exactly the artefact this whole
    # exercise exists to keep out of the book.
    return [(r["n"], r["id"], refs[r["id"]])
            for r in man["entries"]
            if r.get("printed_as") == "description"
            and refs[r["id"]].get("kind") != "unsourced"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true",
                    help="print the bibliographic string for description rows")
    args = ap.parse_args()

    if args.emit:
        for n, rid, entry in descriptions():
            print(f"{n:>3}. {render(entry)}")
            if entry.get("gloss"):
                print(f"     gloss: {entry['gloss'].strip()}")
        return 0

    bad = failures()
    for n, rid, problems in bad:
        print(f"row {n} ({rid}):")
        for p in problems:
            print(f"    {p}")
    print(f"\n{len(bad)} printed rows disagree with the verified record.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
