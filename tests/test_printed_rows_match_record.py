"""The printed appendix may not disagree with the verified record.

``tests/test_appendix_d_manifest.py`` checks that the two lists hold the same
entries. This checks that they say the same things about them.

That gap is where the last defect lived. Printed entry 28 read "Effects of
combinations: mathematical basis of the problem", which is not a publication:
the paper is "Über Kombinationswirkungen", and a reader searching the printed
title finds nothing. The entry was in both lists, under the right id, in the
right chapter, with a DOI that resolved. Every existing check passed. Only
reading the two records side by side found it, and nothing was doing that.

Deliberately a checker and not a generator. Generating the appendix from
``references.yaml`` would remove the disagreement by removing the second
record, and a single source of truth agrees with its own errors. Both defects
this repository found were found by disagreement: 47 entries against 74, and
printed rows 67 and 69 frozen while the yaml moved on. So this compares the two
and reports, rather than making one a function of the other.

Only the bibliographic half is checked - authors, title, venue, volume, pages,
year, DOI, arXiv id. Prose, ordering and grouping belong to the author and are
not the kind of thing a test should have opinions about.

Two escape hatches, both explicit and both per row in the manifest:

  * ``printed_as: description`` for rows that still print a description of a
    finding rather than a citation. They carry no title or author to compare.
    ``python tools/appendix_render.py --emit`` prints the string that turns one
    into a citation.
  * ``omits: [pages, year]`` for fields the printed row deliberately does not
    carry. The house style prints a DOI on some rows and not others, omits
    pages on a working paper, and dates no documentation. Omission is an
    editorial choice; contradiction is the error. Naming the field per row
    keeps the choice visible instead of relaxing the check for everybody.

Both are counted and asserted, so neither can quietly grow.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "references" / "appendix_d.manifest.yaml"

# Loaded by path rather than imported as a package: tools/ has no __init__.py,
# and conftest.py rewrites sys.path per build, so a plain import is fragile.
_spec = importlib.util.spec_from_file_location(
    "appendix_render", REPO / "tools" / "appendix_render.py")
appendix_render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(appendix_render)

# The number of rows still printed as a description, and the number carrying a
# declared omission. Asserted so that neither can grow without somebody
# changing this line and saying why in the commit.
EXPECTED_DESCRIPTIONS = 1
EXPECTED_OMISSIONS = 5


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["appendix_d"]


def test_no_printed_row_contradicts_the_record() -> None:
    """The assertion the whole file exists for."""
    bad = appendix_render.failures()
    assert not bad, "the printed appendix disagrees with references.yaml:\n" + "\n".join(
        f"  row {n} ({rid}):\n" + "\n".join(f"      {p}" for p in problems)
        for n, rid, problems in bad
    )


def test_description_rows_are_declared_and_not_growing(manifest: dict) -> None:
    """A row may not quietly stop being checked.

    Every one of these is a row the author still has to convert from a
    description into a citation. The count going up means a citation regressed
    into a description, which is the direction this project has been fighting.
    """
    rows = [r["n"] for r in manifest["entries"]
            if r.get("printed_as") == "description"]
    assert len(rows) == EXPECTED_DESCRIPTIONS, (
        f"{len(rows)} rows are printed as a description, expected "
        f"{EXPECTED_DESCRIPTIONS}: {sorted(rows)}. If you converted one to a "
        "citation, lower EXPECTED_DESCRIPTIONS. If this went up, a citation "
        "regressed into a description and that is a bug, not a number to edit."
    )


def test_field_omissions_are_declared_and_not_growing(manifest: dict) -> None:
    """Same reasoning, one level finer: per field rather than per row."""
    declared = {r["n"]: r["omits"] for r in manifest["entries"] if r.get("omits")}
    assert len(declared) == EXPECTED_OMISSIONS, (
        f"{len(declared)} rows declare an omitted field, expected "
        f"{EXPECTED_OMISSIONS}: {declared}. Adding one is how this check gets "
        "quietly switched off, so it needs a deliberate edit here."
    )
    known = {"year", "volume", "pages", "arxiv"}
    unknown = {n: [f for f in fields if f not in known]
               for n, fields in declared.items()
               if any(f not in known for f in fields)}
    assert not unknown, (
        f"omits names fields the checker does not check, so they do nothing: "
        f"{unknown}. Note that title, authors and DOI cannot be omitted: they "
        "are the fields this check exists to protect."
    )


def test_renderer_round_trips_a_known_row() -> None:
    """The renderer is what --emit hands the author, so it is checked too.

    Chosen because it exercises every branch that matters: an author list, a
    volume, a page range printed as "716 to 723" rather than with a dash, a
    year in parentheses and a DOI.
    """
    entries = {e["id"]: e for e in yaml.safe_load(
        (REPO / "references" / "references.yaml").read_text(encoding="utf-8")
    )["references"]}
    rendered = appendix_render.render(entries["swanson2025virtuallab"])
    assert rendered == (
        "Swanson, K., Wu, W., Bulaong, N. L., Pak, J. E. and Zou, J. "
        "The Virtual Lab of AI agents designs new SARS-CoV-2 nanobodies. "
        "Nature 646, 716 to 723 (2025). doi:10.1038/s41586-025-09442-9."
    ), rendered


def test_gloss_never_carries_maintenance_prose() -> None:
    """gloss prints; note does not. Getting that backwards ships scaffolding.

    The maintenance notes in references.yaml say things like "THE ENTRY IS
    STALE AND THE FIX IS NOT MINE TO MAKE" and "Only the abstract was read
    here". Those exist to stop the next person repeating work. In a printed
    book they would be a disaster, so the phrases that mark them are barred
    from the field that prints.
    """
    entries = yaml.safe_load(
        (REPO / "references" / "references.yaml").read_text(encoding="utf-8")
    )["references"]
    banned = ("appendix d reads", "appendix d calls this", "crossref returns",
              "resolved by the finding", "resolved on the finding",
              "not mine to make", "confirm this is the right paper",
              "only the abstract", "unsourced", "still unsourced")
    leaks = []
    for entry in entries:
        gloss = (entry.get("gloss") or "").lower()
        hits = [phrase for phrase in banned if phrase in gloss]
        if hits:
            leaks.append((entry["id"], hits))
    assert not leaks, (
        "maintenance prose has leaked into a gloss, which is the field that "
        f"prints in the book: {leaks}"
    )


def test_emit_survives_a_console_that_cannot_spell_the_authors() -> None:
    """--emit must not be at the mercy of the console codepage.

    Found by running the documented command on a plain Windows console. The
    default there is cp1252, which cannot encode "Mäntylä" or "Seifert-Dähnn",
    and the failure mode was worse than a crash: Python emitted replacement
    bytes for the rows it could mangle, printed them, and only then raised
    UnicodeEncodeError partway down the list. The output up to that point
    looked usable and was corrupted in precisely the author names nobody would
    re-check, which is the defect class this whole file exists to prevent.

    Rendering these strings is the last step before they are pasted into a
    book, so it is the last place an encoding should be left to chance.

    Driven through --all rather than the bare --emit. The first version of this
    test used --emit, and it broke the moment the last diacritic-carrying
    description row was pasted into the appendix and stopped being emitted: the
    test was silently coupled to which rows happened to be outstanding. --all
    always renders every entry, so the encoding is tested rather than the
    backlog.
    """
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "appendix_render.py"),
         "--emit", "--all"],
        capture_output=True, env=env, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    out = proc.stdout.decode("utf-8")
    for name in ("Mäntylä", "Seifert-Dähnn", "López-Muñoz", "Łaźniewski", "Hornbæk"):
        assert name in out, f"{name} did not survive a cp1252 console"
    assert "�" not in out and "?" * 2 not in out.replace("Both?", "")
