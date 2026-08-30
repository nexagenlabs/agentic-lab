"""The thirteen printed URLs, checked against what the repository holds.

A URL printed in a book cannot be corrected. Once the run is bound, the only
thing left that can move is the redirect behind it, so the redirect had better
point somewhere real. These tests exist because the failure they catch is
silent: `site/_redirects` is a text file nothing validates, a destination can
be renamed by a refactor three folders away, and nobody finds out until a
reader types an address off a page and lands on a 404.

Three assertions, and the third is the one that matters.

1. Every printed path has a rule. The list below is the contract, and it is
   duplicated here on purpose rather than parsed out of the site, because a
   test that reads its expectations from the thing under test asserts only
   that the file agrees with itself.

2. No rule exists for /ch01 or /ch02. Chapters 1 and 2 ship no code. Inventing
   a destination for them would send a reader to the wrong build, which is
   worse than the 404 page, because a wrong build looks like an answer.

3. Every destination is a path that exists in this repository. A redirect to a
   folder that does not exist is a dead link in a printed book.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
REDIRECTS = SITE / "_redirects"

GITHUB = "https://github.com/nexagenlabs/agentic-lab"
GITHUB_PATH = re.compile(
    rf"^{re.escape(GITHUB)}/(?:tree|blob)/main/(?P<path>.+)$"
)

# The contract. Thirteen paths, no more and no fewer.
PRINTED_PATHS = (
    "/",
    "/setup",
    "/ch03",
    "/ch04",
    "/ch05",
    "/ch06",
    "/ch07",
    "/ch08",
    "/ch09",
    "/ch10",
    "/ch11",
    "/ch12",
    "/references",
)

NEVER_PRINTED = ("/ch01", "/ch02")


def rules() -> dict[str, tuple[str, str]]:
    """Every rule in _redirects, as {source: (destination, status)}."""
    parsed: dict[str, tuple[str, str]] = {}
    for line in REDIRECTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        assert len(parts) == 3, f"a rule needs source, target and status: {line!r}"
        source, target, status = parts
        assert source not in parsed, f"{source} has two rules"
        parsed[source] = (target, status)
    return parsed


def repository_path(destination: str) -> Path | None:
    """The repository path a destination points at, or None if it points off it.

    Two shapes resolve: a GitHub tree or blob URL under this repository, and a
    site-relative path, which is a file under site/. Anything else is a
    destination this test cannot vouch for, and it says so rather than passing
    quietly.
    """
    match = GITHUB_PATH.match(destination)
    if match:
        return REPO_ROOT / match.group("path")
    if destination.startswith("/"):
        return SITE / destination.lstrip("/")
    return None


def test_the_site_exists():
    assert SITE.is_dir(), "there is no site/ folder"
    for name in ("index.html", "_redirects", "errata.html", "404.html"):
        assert (SITE / name).is_file(), f"site/{name} is missing"


def test_every_printed_url_has_a_rule():
    """The thirteen the book prints, each with somewhere to go."""
    configured = rules()
    missing = [path for path in PRINTED_PATHS if path not in configured]
    assert not missing, (
        f"these paths are printed in the book and have no rule: {missing}. "
        "A reader typing one gets the 404 page instead of the build."
    )


def test_no_rule_invents_a_chapter_that_ships_no_code():
    """Chapters 1 and 2 ship nothing, so nothing may claim to serve them."""
    configured = rules()
    for path in NEVER_PRINTED:
        assert path not in configured, (
            f"{path} has a rule. Chapters 1 and 2 ship no code, and sending a "
            "reader to a build anyway is worse than the 404 page: a wrong "
            "build looks like an answer."
        )
    # And no wildcard quietly does the same thing. A /ch* splat would catch
    # ch01 and ch02 without ever naming them.
    for source in configured:
        assert "*" not in source, (
            f"{source} is a wildcard rule. It would swallow /ch01 and /ch02 "
            "and send them somewhere, which is the thing being prevented."
        )


def test_no_rule_exists_that_the_book_does_not_print():
    """The contract runs both ways: nothing here that is not on a page."""
    extra = sorted(set(rules()) - set(PRINTED_PATHS))
    assert not extra, (
        f"these rules are not printed anywhere in the book: {extra}. An "
        "address nobody can find is an address nobody maintains."
    )


@pytest.mark.parametrize("path", PRINTED_PATHS)
def test_every_destination_exists_in_the_repository(path: str):
    """The one that matters. A dead destination is a dead link in print."""
    destination, _status = rules()[path]
    target = repository_path(destination)
    assert target is not None, (
        f"{path} points at {destination}, which this test cannot resolve to a "
        "repository path, so nothing is checking that it exists."
    )
    assert target.exists(), (
        f"{path} points at {destination}, and {target.relative_to(REPO_ROOT)} "
        "does not exist in this repository. That is a dead link in a printed "
        "book."
    )


def test_redirects_are_temporary_so_a_correction_can_reach_a_reader():
    """302, not 301. A permanent redirect is cached and cannot be corrected.

    The reader who most needs a fixed destination is the one who already
    followed the printed URL, and a 301 is exactly the response that makes
    their browser never ask again.
    """
    for source, (destination, status) in rules().items():
        if source == "/":
            # The hub is a rewrite, not a redirect: the reader keeps the URL
            # they typed and the file is served under it.
            assert status == "200", f"the hub should be a rewrite, got {status}"
            continue
        assert status == "302", (
            f"{source} redirects with {status}. Use 302: a 301 is cached by "
            f"the browser, so a reader who visited {source} once would keep "
            "going to the old destination after it was corrected, with no way "
            "to know."
        )
        assert destination.startswith("https://"), (
            f"{source} points at {destination}, which is not an absolute URL"
        )


def flatten(text: str) -> str:
    """Lowercase, alphanumerics only.

    Compared this way because the folder name cannot tell you how the name is
    written: `09-eln-bridge` title-cases to "Eln Bridge" and the page quite
    rightly says "ELN Bridge". The test should assert the build is listed, not
    dictate its capitalisation.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def test_the_hub_lists_every_build():
    """A build the hub does not mention is a build a reader cannot find."""
    hub = flatten((SITE / "index.html").read_text(encoding="utf-8"))
    builds = sorted(p.name for p in (REPO_ROOT / "builds").iterdir()
                    if p.is_dir() and not p.name.startswith("_"))
    assert len(builds) == 12
    for build in builds:
        assert flatten(build) in hub, f"the hub does not list {build}"


def test_the_hub_and_the_404_say_why_there_is_no_ch01():
    """The absence is deliberate, so both pages that could confuse say so."""
    for name in ("index.html", "404.html"):
        page = (SITE / name).read_text(encoding="utf-8")
        assert "ch01" in page and "ch02" in page, (
            f"site/{name} does not mention the two chapters that ship no "
            "code, so a reader who tried one learns nothing from it"
        )


def test_the_errata_page_is_ready_to_receive_one():
    """Empty is fine. Missing the structure is not."""
    page = (SITE / "errata.html").read_text(encoding="utf-8")
    for column in ("Printing", "Page", "Description", "Correction"):
        assert f"<th>{column}</th>" in page, f"no {column} column"
    assert "issues" in page and "mailto:" in page, (
        "the errata page does not say how to report one"
    )


def test_the_site_needs_no_build_step_and_no_javascript():
    """Plain HTML, so it cannot rot between printings.

    The book will outlive any toolchain this site could have depended on, and
    a static page that needs nothing to serve it is the only version certain
    to still work when somebody follows a printed URL years from now.
    """
    for name in ("index.html", "errata.html", "404.html"):
        page = (SITE / name).read_text(encoding="utf-8")
        assert "<script" not in page.lower(), f"site/{name} contains script"
        assert "</html>" in page, f"site/{name} is not a complete document"
        assert 'name="viewport"' in page, f"site/{name} is not readable on a phone"
