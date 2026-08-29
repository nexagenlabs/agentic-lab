"""Listing conformance: does the repository still match the printed book?

The most damaging defect this project can ship is a code listing on a printed
page that no longer matches the repository, because a reader typing from the
page gets a different result and cannot tell why. Print is not patchable.

This test asserts that every listing printed in the book appears in the file
it is supposed to appear in. It is the automated half of a check that was
previously done by eye.

Run it with:

    python -m pytest tests/test_listings.py -v

A failure prints a line-by-line report of what the book says and what the
repository says, so you can decide which one is wrong. Sometimes the answer
is the book.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "listings" / "manifest.yaml"


def normalise(text: str) -> list[str]:
    """Reduce a listing to the lines that must match.

    Trailing whitespace, blank lines and full-line comments are dropped.
    The book adds explanatory comments that the repository does not need,
    and a difference in either is not a defect worth failing a build over.
    """
    out = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return out


def load_entries() -> list[dict]:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return data["listings"]


def entry_id(entry: dict) -> str:
    return Path(entry["file"]).stem


ENTRIES = load_entries()


def test_manifest_covers_every_listing_file():
    """No listing may sit in the repository unreferenced by the manifest.

    A listing nobody checks is a listing that will drift.
    """
    on_disk = {
        str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        for p in (REPO_ROOT / "listings").rglob("*.txt")
    }
    in_manifest = {e["file"] for e in ENTRIES}
    missing = on_disk - in_manifest
    assert not missing, (
        "These listing files are not referenced by listings/manifest.yaml: "
        f"{sorted(missing)}"
    )


@pytest.mark.parametrize("entry", ENTRIES, ids=[entry_id(e) for e in ENTRIES])
def test_listing_matches_repository(entry: dict):
    mode = entry["mode"]

    if mode == "skip":
        pytest.skip(entry.get("note", "skipped by manifest"))

    listing_path = REPO_ROOT / entry["file"]
    target_path = REPO_ROOT / entry["target"]

    assert listing_path.exists(), f"Listing file missing: {entry['file']}"
    assert target_path.exists(), (
        f"Target file missing: {entry['target']}. The book prints a listing "
        f"for it under the heading {entry.get('heading', '')!r}."
    )

    printed = normalise(listing_path.read_text(encoding="utf-8"))
    actual = normalise(target_path.read_text(encoding="utf-8"))

    assert printed, f"Listing {entry['file']} is empty after normalisation"

    if mode == "exact":
        ok = _contains_block(actual, printed)
        if not ok:
            pytest.fail(_report(entry, printed, actual, "verbatim block"))

    elif mode == "fragment":
        missing = _missing_in_order(actual, printed)
        if missing:
            pytest.fail(
                _report(entry, printed, actual, "ordered fragment")
                + "\n\nFirst lines not found in order:\n"
                + "\n".join(f"    {line}" for line in missing[:8])
            )

    else:
        pytest.fail(f"Unknown mode {mode!r} in manifest for {entry['file']}")


def _contains_block(haystack: list[str], needle: list[str]) -> bool:
    """Does needle appear as a contiguous run of lines inside haystack?"""
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    for i in range(len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return True
    return False


def _missing_in_order(haystack: list[str], needle: list[str]) -> list[str]:
    """Which needle lines do not appear in haystack, in order?"""
    missing = []
    cursor = 0
    for line in needle:
        try:
            cursor = haystack.index(line, cursor) + 1
        except ValueError:
            missing.append(line)
    return missing


def _report(entry: dict, printed: list[str], actual: list[str], kind: str) -> str:
    diff = difflib.unified_diff(
        printed,
        actual,
        fromfile=f"BOOK  {entry['file']}",
        tofile=f"REPO  {entry['target']}",
        lineterm="",
        n=2,
    )
    return (
        f"\nListing drift, {kind} check failed.\n"
        f"  Chapter {entry.get('chapter')}, heading "
        f"{entry.get('heading', '')!r}\n"
        f"  Book listing:     {entry['file']}\n"
        f"  Repository file:  {entry['target']}\n\n"
        "A reader typing the printed listing would not get the repository "
        "file. Decide which one is wrong, fix it, and if the book is wrong "
        "record it in the errata.\n\n"
        + "\n".join(diff)
    )
