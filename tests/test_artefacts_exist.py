"""Every path the book names, checked against the repository.

CLAIMS.md covers what the book says the code does. Nothing covered what the
book says the repository contains, and that is the gap this session walked
into: Appendix B prints a tree listing three templates, and two of them did
not exist. A reader following a printed tree gets a missing file, which is a
worse first impression than a missing feature, because it says the tree was
never checked.

Two assertions, and the second is the one people leave out. A path must exist,
and it must not be empty. A zero byte file passes every existence check ever
written and fails the reader immediately, and it is exactly what a half
finished commit or a bad merge leaves behind.

Failures are collected rather than raised one at a time. At layout you want the
whole list, not the first name on it.

Artefacts that the book names and that do not exist yet are recorded in
ABSENT, with the same rule the mutation gate uses for its survivors: each must
still be absent, so the moment somebody writes one this gate fails and asks for
it to be moved into ARTEFACTS. A recorded absence is a finding kept in view,
never permission to stay missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

BUILDS = (
    "01-first-agent", "02-tool-belt", "03-triage-agent", "04-dual-screen",
    "05-wrangler", "06-plate-mapper", "07-protocol-adapter", "08-dock-loop",
    "09-eln-bridge", "10-run-manifest", "11-red-team", "12-repurposing-desk",
)

# The thirteen printed URLs each carry a code that goes to the printer with
# the page. A code missing at layout is a page that ships without one.
QR_CODES = (
    "ch03", "ch04", "ch05", "ch06", "ch07", "ch08", "ch09", "ch10", "ch11",
    "ch12", "hub", "references", "setup",
)

TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".txt", ".html", ""}


@dataclass(frozen=True)
class Artefact:
    """One path the book names, and where it names it."""

    path: str
    named_by: str
    kind: str = "file"

    def resolve(self) -> Path:
        return REPO / self.path


def _artefacts() -> tuple[Artefact, ...]:
    named: list[Artefact] = [
        # The setup a reader follows before anything else.
        Artefact("README.md", "Chapter 1, and the /setup URL redirects here"),
        Artefact("LICENSE", "the front matter"),
        Artefact("requirements.txt", "Chapter 1's install instruction"),
        Artefact("requirements.lock.txt", "Chapter 1, the tested versions"),
        Artefact("MODELS.md", "Chapter 2, and README.md sends readers to it"),
        Artefact("CLAUDE.md", "Appendix B, the standing instructions"),

        # Chapter 11 ships paperwork rather than a build, and Chapter 2 and
        # Chapter 4 each contribute a template to the same folder.
        Artefact("templates/README.md", "Appendix B's tree"),
        Artefact("templates/context_of_use.md", "Chapter 11, the one page"),
        Artefact("templates/screen_report.md", "Chapter 4, pasteable"),
        Artefact("templates/stack.yaml", "Chapter 2, the Stack Inventory"),

        # The companion site behind the thirteen printed URLs.
        Artefact("site/index.html", "lab.nexagenlabs.com, the hub"),
        Artefact("site/_redirects", "every printed chapter URL"),
        Artefact("site/404.html", "the never-printed paths, /ch01 and /ch02"),
        Artefact("site/errata.html", "README.md's errata link"),

        # Run by hand or in CI, never by pytest.
        Artefact("tools/verify_references.py", "Appendix D, the reference check"),
        Artefact("tools/verify_printed_urls.py", "Chapter 12's tooling note"),
        Artefact("tools/generate_qr_codes.py", "the production step at layout"),

        # Appendix D.
        Artefact("references/references.yaml", "Appendix D, the bibliography"),
        Artefact("references/references_report.md", "Appendix D, resolved"),
        Artefact("references/references_resolved.json", "Appendix D, the records"),

        # The printed listings and their conformance manifest.
        Artefact("listings/manifest.yaml", "every printed code listing"),
        Artefact("listings", "Appendix B's tree", "dir"),

        Artefact("qr/README.md", "the layout instructions for the codes"),
    ]

    named += [Artefact(f"qr/{name}.png", f"the code printed beside {name}")
              for name in QR_CODES]

    for build in BUILDS:
        named += [
            Artefact(f"builds/{build}", "Appendix B's tree", "dir"),
            Artefact(f"builds/{build}/README.md", "the build's own chapter"),
            Artefact(f"builds/{build}/SPEC.md", "Appendix B, one spec per build"),
            Artefact(f"builds/{build}/stack.yaml", "Chapter 2, emitted per build"),
            Artefact(f"builds/{build}/stack.py", "Chapter 2, the emitter"),
            Artefact(f"builds/{build}/tests", "Appendix B, one gate per build",
                     "dir"),
        ]

    return tuple(named)


ARTEFACTS = _artefacts()

# Named by the book and not in the repository. Each entry is a finding, not a
# dispensation, and a test below fails the moment one of these appears so it
# cannot sit here once it exists.
ABSENT: tuple[Artefact, ...] = (
    Artefact(
        "check_setup.py",
        "the author's manifest of printed paths. Nothing in site/_redirects "
        "or the printed URL map points at it: /setup redirects to README.md. "
        "Either the book names a file that was never written, or it names it "
        "under a path this repository does not use.",
    ),
)


def _is_empty(path: Path) -> bool:
    """Empty enough to fail a reader, not only empty on disk."""
    if path.is_dir():
        return not any(path.iterdir())
    if path.stat().st_size == 0:
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return not path.read_text(encoding="utf-8", errors="replace").strip()
    return False


def test_every_artefact_the_book_names_exists():
    """The whole list, because at layout you want every name at once."""
    missing = [item for item in ARTEFACTS if not item.resolve().exists()]
    assert not missing, (
        "The book names these paths and the repository does not have them:\n"
        + "\n".join(f"  {item.path}\n      named by {item.named_by}"
                    for item in missing)
        + "\n\nA reader following a printed tree finds nothing there. Either "
        "write the file or change the page, and the page is the expensive "
        "half to change."
    )


def test_no_artefact_the_book_names_is_empty():
    """A zero byte file passes an existence check and fails a reader."""
    present = [item for item in ARTEFACTS if item.resolve().exists()]
    empty = [item for item in present if _is_empty(item.resolve())]
    assert not empty, (
        "These paths exist and hold nothing:\n"
        + "\n".join(f"  {item.path} ({item.kind})" for item in empty)
        + "\n\nAn empty file is what a half finished commit leaves behind, "
        "and it is indistinguishable from a working one until somebody opens "
        "it."
    )


@pytest.mark.parametrize("item", ABSENT, ids=[item.path for item in ABSENT])
def test_a_recorded_absence_is_still_absent(item: Artefact):
    """Good news arrives here as a failure.

    When a recorded absence appears, this fails and asks for it to be moved
    into ARTEFACTS, where it is checked like everything else. Without this the
    list would be an allowlist for missing files, which is the shape the rest
    of this gate exists to prevent.
    """
    assert not item.resolve().exists(), (
        f"{item.path} now exists, and this file records it as missing.\n"
        "Move its entry from ABSENT into ARTEFACTS so it is checked for "
        "content as well as for presence."
    )


def test_the_manifest_covers_every_build():
    """A thirteenth build must be listed here rather than quietly skipped."""
    on_disk = {
        path.name for path in (REPO / "builds").iterdir()
        if path.is_dir() and not path.name.startswith((".", "_"))
    }
    assert on_disk == set(BUILDS), (
        f"builds/ holds {sorted(on_disk)} and this manifest lists "
        f"{sorted(BUILDS)}. A build nobody listed is a build whose README, "
        "spec and inventory nothing checks for."
    )
