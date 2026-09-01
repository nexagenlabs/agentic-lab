"""Appendix D and references.yaml are one list, checked rather than assumed.

This test exists because of a failure that ran the whole length of the first
draft, and it is the kind of failure a verification tool makes *more* likely
rather than less.

``references.yaml`` was seeded by hand and never reconciled against Appendix D
of the manuscript. The appendix carried 74 entries; the file carried 47.
``tools/verify_references.py`` resolved those 47 against Crossref, reported
that every reachable entry was confirmed, and exited zero. Three separate
passes read that green result as a statement about the printed book. It was
not. It was a statement about the 47 entries the tool could see, and the
twenty-two that shipped in the book had never been checked by anything.

A gate pointed at the wrong list is worse than no gate, because a missing gate
leaves you uncertain and a misaimed one sells you confidence it has not earned.
That is the same defect as a fabricated citation: something that looks right is
doing the work of something that is right.

The manuscript is not in this repository, so nothing here can read the
appendix. ``references/appendix_d.manifest.yaml`` stands in for it: a
hand-transcribed record of what the printed page holds. That is a weaker
witness than the page itself, and it is chosen deliberately over the
alternatives.

Why this shape:

  * **A count stated separately from the list.** The manifest names 74 as a
    bare number, not as ``len(entries)``. Derived from the list it would be
    vacuous, and a row deleted from both files at once would pass. Stated on
    its own it is an independent witness, and it is what catches a whole entry
    going missing, which is precisely what went wrong.
  * **Set equality in both directions**, not containment. The original bug was
    one-directional, references.yaml being a subset, and a containment check in
    the convenient direction would have passed throughout.
  * **A short phrase per entry, anchored back into references.yaml.** The
    phrase is what lets a person find the entry on the printed page. Requiring
    it to appear in that entry's id, title or note means an entry cannot be
    resolved from a description into a real paper without recording what the
    appendix itself says. Several entries here were descriptions of findings,
    and their resolved titles deliberately do not match the appendix wording;
    asserting equality of title and phrase would have forced them back into
    agreement in the wrong direction, by corrupting the resolved title.

What this test cannot do: it cannot tell you the manifest is a faithful
transcription. Nothing in a repository can, while the manuscript is outside it.
It can only ensure the two lists that *are* here never drift apart again, and
that the drift already found stays visible until someone reads the page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
REFERENCES = REPO / "references" / "references.yaml"
MANIFEST = REPO / "references" / "appendix_d.manifest.yaml"


def _norm(text: str) -> str:
    """Compare on words alone.

    Punctuation is exactly what differs between a phrase transcribed off a
    printed page and the same phrase retyped into a note: a middle dot for a
    decimal point, a tilde for "approximately", curly quotes, an en dash. None
    of those change which entry is being named, and a test that failed on them
    would be retrained into uselessness within a week.
    """
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    return yaml.safe_load(REFERENCES.read_text(encoding="utf-8"))["references"]


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["appendix_d"]


def test_manifest_ids_are_unique(manifest: dict) -> None:
    ids = [row["id"] for row in manifest["entries"]]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"manifest lists these ids more than once: {duplicates}"


def test_manifest_phrases_are_present_and_distinct(manifest: dict) -> None:
    """A blank or duplicated phrase makes a row unfindable on the page."""
    blank = [row["id"] for row in manifest["entries"] if not row.get("phrase", "").strip()]
    assert not blank, f"manifest rows with no identifying phrase: {blank}"

    seen: dict[str, list[str]] = {}
    for row in manifest["entries"]:
        seen.setdefault(_norm(row["phrase"]), []).append(row["id"])
    collisions = {phrase: ids for phrase, ids in seen.items() if len(ids) > 1}
    assert not collisions, (
        "two appendix entries share an identifying phrase, so the manifest "
        f"cannot distinguish them: {collisions}"
    )


def test_manifest_accounts_for_every_printed_appendix_entry(manifest: dict) -> None:
    """The count is the independent witness. It is stated, not derived.

    This is the assertion that would have caught the original drift on the day
    it happened, and as of this writing it FAILS: the appendix is counted at 74
    and only 69 entries have been transcribed. Do not resolve that by lowering
    the count. Read the printed appendix and transcribe the five that are
    missing, or correct the count against the page if the count is what is
    wrong.
    """
    counted = manifest["count"]
    transcribed = len(manifest["entries"])
    assert transcribed == counted, (
        f"Appendix D is counted at {counted} entries but only {transcribed} are "
        f"transcribed in {MANIFEST.name}, a shortfall of {counted - transcribed}. "
        "Every entry in the printed appendix must appear here, or nothing "
        "downstream is checking the printed book."
    )


def test_references_yaml_holds_exactly_the_appendix_list(
    entries: list[dict], manifest: dict
) -> None:
    """Set equality, both directions. Containment either way hides the bug."""
    in_yaml = {entry["id"] for entry in entries}
    in_appendix = {row["id"] for row in manifest["entries"]}

    missing = sorted(in_appendix - in_yaml)
    extra = sorted(in_yaml - in_appendix)
    assert not missing, (
        f"in Appendix D but absent from references.yaml, so never verified "
        f"by anything: {missing}"
    )
    assert not extra, (
        f"in references.yaml but not in Appendix D. Either the appendix "
        f"transcription is incomplete or the book does not cite these: {extra}"
    )


def test_every_appendix_phrase_is_recorded_in_its_entry(
    entries: list[dict], manifest: dict
) -> None:
    """An entry may not be resolved without recording the appendix's wording.

    Where Appendix D gives a description rather than a title, resolving the
    entry replaces that description with the real title, and the trail back to
    the printed page is gone unless something keeps it. The note keeps it.
    """
    by_id = {entry["id"]: entry for entry in entries}
    unanchored = []
    for row in manifest["entries"]:
        entry = by_id.get(row["id"])
        if entry is None:
            continue          # already reported by the set-equality test
        haystack = _norm(" ".join([
            entry["id"],
            entry.get("title", "") or "",
            entry.get("note", "") or "",
        ]))
        if _norm(row["phrase"]) not in haystack:
            unanchored.append((row["id"], row["phrase"]))

    assert not unanchored, (
        "these entries do not record the wording Appendix D uses for them, so "
        "nobody can check the resolution against the printed page. Quote the "
        "appendix phrase in the entry's note: "
        + "; ".join(f"{i} -> {p!r}" for i, p in unanchored)
    )


def test_chapter_numbers_agree(entries: list[dict], manifest: dict) -> None:
    """A row that migrates chapters in one file and not the other is drift too."""
    by_id = {entry["id"]: entry for entry in entries}
    mismatched = [
        (row["id"], row.get("chapter"), by_id[row["id"]].get("chapter"))
        for row in manifest["entries"]
        if row["id"] in by_id and row.get("chapter") != by_id[row["id"]].get("chapter")
    ]
    assert not mismatched, (
        "chapter disagrees between the manifest and references.yaml for: "
        + "; ".join(f"{i} (appendix {a}, yaml {y})" for i, a, y in mismatched)
    )
