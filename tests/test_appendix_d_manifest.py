"""Appendix D and references.yaml are one list, checked rather than assumed.

This test exists because of a failure that ran the whole length of the first
draft, and it is the kind of failure a verification tool makes *more* likely
rather than less.

``references.yaml`` was seeded by hand and never reconciled against Appendix D
of the manuscript. The appendix carried 74 printed rows; the file carried 47.
``tools/verify_references.py`` resolved those 47 against Crossref, reported
that every reachable entry was confirmed, and exited zero. Three separate
passes read that green result as a statement about the printed book. It was
not. It was a statement about the 47 entries the tool could see, and the rest
had never been checked by anything.

A gate aimed at the wrong list is worse than no gate, because a missing gate
leaves you uncertain and a misaimed one sells you confidence it has not
earned. That is the same defect as a fabricated citation, one rung up:
something that looks right doing the work of something that is right.

Drift runs in both directions, and this test has now caught it going the other
way. Printed entries 67 and 69 still carry descriptions that ``references.yaml``
resolved to real papers two passes ago: the yaml moved forward and the page did
not. Those are recorded in the entries' notes rather than papered over.

Seventy-four printed rows describe seventy-three distinct works. Entries 8 and
63 are the same FDA/EMA document, printed once in Chapter 1 and again in
Chapter 11. The manifest records the repeat with ``duplicate_of`` rather than
collapsing it, because the printed page really does have 74 numbered rows and a
manifest holding 73 would disagree with anyone counting the book.

The manuscript is not in this repository, so nothing here can read the
appendix. ``references/appendix_d.manifest.yaml`` stands in for it, transcribed
from ``references/APPENDIX_D_AS_PRINTED.md``. That is a weaker witness than the
page itself, and the shape is chosen around that weakness:

  * **A count stated separately from the list.** The manifest names 74 as a
    bare number, not as ``len(entries)``. Derived from the list it would be
    vacuous, and a row deleted from both files at once would pass. Stated on
    its own it is an independent witness, and it is what caught the original
    shortfall.
  * **Printed numbering asserted contiguous.** A second independent witness. A
    row can go missing from the middle of a transcription without changing
    anything else, and a gap in 1..74 says so immediately.
  * **Set equality in both directions**, not containment. The original bug was
    one-directional, references.yaml being a subset, and a containment check in
    the convenient direction would have passed throughout the draft.
  * **A short phrase per entry, anchored back into references.yaml.** The
    phrase is what lets a person find the row on the printed page. Requiring it
    to appear in that entry's id, title or note means an entry cannot be
    resolved from a description into a real paper without recording what the
    appendix itself says. Several entries here were descriptions of findings,
    and their resolved titles deliberately do not match the appendix wording;
    asserting equality of title and phrase would have forced them back into
    agreement in the wrong direction, by corrupting the resolved title back
    into the description.

What this test cannot do: it cannot tell you the transcription is faithful.
Nothing in a repository can, while the manuscript is outside it. It can only
ensure the lists that *are* here never drift apart again.
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


def test_manifest_accounts_for_every_printed_appendix_row(manifest: dict) -> None:
    """The count is the independent witness. It is stated, not derived.

    This is the assertion that would have caught the original drift on the day
    it happened, and the one that found the five-row shortfall. Never resolve a
    failure here by editing the count down to match the list: read the printed
    appendix and transcribe what is missing, or correct the count against the
    page if the count is what is wrong.
    """
    counted, transcribed = manifest["count"], len(manifest["entries"])
    assert transcribed == counted, (
        f"Appendix D is counted at {counted} printed rows but {transcribed} are "
        f"transcribed in {MANIFEST.name}, a difference of {counted - transcribed}. "
        "Every row in the printed appendix must appear here, or nothing "
        "downstream is checking the printed book."
    )


def test_printed_numbering_is_contiguous(manifest: dict) -> None:
    """A row lost from the middle of the transcription shows up as a gap."""
    numbers = [row["n"] for row in manifest["entries"]]
    expected = list(range(1, manifest["count"] + 1))
    assert numbers == expected, (
        "printed entry numbers are not 1.."
        f"{manifest['count']} in order. Missing: {sorted(set(expected) - set(numbers))}; "
        f"unexpected: {sorted(set(numbers) - set(expected))}"
    )


def test_repeated_rows_are_declared(manifest: dict) -> None:
    """An id may appear twice only where the appendix prints the work twice."""
    by_n = {row["n"]: row for row in manifest["entries"]}
    seen: dict[str, list[int]] = {}
    for row in manifest["entries"]:
        if "duplicate_of" not in row:
            seen.setdefault(row["id"], []).append(row["n"])
    repeated = {i: ns for i, ns in seen.items() if len(ns) > 1}
    assert not repeated, (
        "these ids appear on more than one printed row without being declared "
        f"a repeat: {repeated}. If the appendix really prints the work twice, "
        "mark the later row duplicate_of the earlier one."
    )

    for row in manifest["entries"]:
        original = row.get("duplicate_of")
        if original is None:
            continue
        assert original in by_n, (
            f"row {row['n']} claims to duplicate row {original}, which does not exist"
        )
        assert original < row["n"], (
            f"row {row['n']} should duplicate an earlier row, not row {original}"
        )
        assert by_n[original]["id"] == row["id"], (
            f"row {row['n']} is marked a duplicate of row {original}, but they "
            f"name different works: {row['id']} against {by_n[original]['id']}"
        )


def test_manifest_phrases_are_present_and_distinct(manifest: dict) -> None:
    """A blank or accidentally shared phrase makes a row unfindable."""
    blank = [r["n"] for r in manifest["entries"] if not r.get("phrase", "").strip()]
    assert not blank, f"printed rows with no identifying phrase: {blank}"

    seen: dict[str, list[int]] = {}
    for row in manifest["entries"]:
        if "duplicate_of" not in row:
            seen.setdefault(_norm(row["phrase"]), []).append(row["n"])
    collisions = {p: ns for p, ns in seen.items() if len(ns) > 1}
    assert not collisions, (
        "two printed rows share an identifying phrase without being declared a "
        f"repeat, so the manifest cannot distinguish them: {collisions}"
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
        f"in Appendix D but absent from references.yaml, so never verified by "
        f"anything: {missing}"
    )
    assert not extra, (
        f"in references.yaml but not in Appendix D. Either the transcription is "
        f"incomplete or the book does not cite these: {extra}"
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
            unanchored.append((row["n"], row["id"], row["phrase"]))

    assert not unanchored, (
        "these entries do not record the wording Appendix D uses for them, so "
        "nobody can check the resolution against the printed page. Quote the "
        "appendix phrase in the entry's note: "
        + "; ".join(f"{n} {i} -> {p!r}" for n, i, p in unanchored)
    )


def test_chapter_numbers_agree(entries: list[dict], manifest: dict) -> None:
    """A row that migrates chapters in one file and not the other is drift too.

    Declared repeats are exempt: the FDA/EMA principles are printed under both
    Chapter 1 and Chapter 11, and references.yaml can only file them once.
    """
    by_id = {entry["id"]: entry for entry in entries}
    mismatched = [
        (row["n"], row["id"], row.get("chapter"), by_id[row["id"]].get("chapter"))
        for row in manifest["entries"]
        if "duplicate_of" not in row
        and row["id"] in by_id
        and row.get("chapter") != by_id[row["id"]].get("chapter")
    ]
    assert not mismatched, (
        "chapter disagrees between the printed appendix and references.yaml for: "
        + "; ".join(f"row {n} {i} (printed {a}, yaml {y})" for n, i, a, y in mismatched)
    )
