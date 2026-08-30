"""Follow every URL printed in the book, over the live internet, and report.

`tests/test_site_urls.py` asserts that `site/_redirects` names a destination
which exists in this repository. That is the check you can run on a train, and
it is not the check that matters on the day the book is printed. It cannot see
DNS, it cannot see TLS, it cannot see whether Netlify deployed, and it cannot
see whether GitHub renamed a URL scheme. It asserts the map. This asserts the
territory.

    python tools/verify_printed_urls.py

Exit code is non-zero if any printed URL fails, so it can gate a print run.

## This is a tool, not a test

It makes real network requests, exactly as `tools/verify_references.py` does,
and the CLAUDE.md rule against live calls governs tests rather than tools. It
is deliberately not in `testpaths` and must never be added: a suite that fails
when the internet is down is a suite people learn to ignore, and the one thing
worse than an unchecked reference list is a checked one nobody reads any more.

Run it by hand before a print run, and in CI on a schedule if you like.

## Certificate failures are reported separately

A dead link in a printed book is bad. A certificate warning is worse, because
the browser blames the author in the strongest language it has, and a reader
who sees "Your connection is not private" on an address from a book does not
conclude that a certificate expired. They conclude the book is not to be
trusted. So a TLS failure is its own status rather than a connection error,
and verification is never disabled anywhere in this file.
"""

from __future__ import annotations

import importlib.util
import json
import ssl
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = "https://lab.nexagenlabs.com"

# The hub serves itself; every chapter path leaves for GitHub.
HUB_HOST = "lab.nexagenlabs.com"
CODE_HOST = "github.com"

# Paths the book never prints. A reader who mistypes one should still land
# somewhere useful rather than dead-ending.
NEVER_PRINTED = ("/ch01", "/ch02")

# A string that appears on the hub and nowhere else, so "did this reach the
# hub" is answered by what was served rather than by the status code alone.
HUB_MARKER = "Which builds belong to which chapter"

TIMEOUT = 30.0


@dataclass
class Result:
    path: str
    requested: str
    status: str          # OK | CERTIFICATE | UNREACHABLE | STATUS | HOST | CONTENT
    http_status: int | None
    final_url: str | None
    final_host: str | None
    redirects: int
    note: str

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def printed_paths() -> tuple[str, ...]:
    """The thirteen, read from the test that already pins them.

    Not copied. A second copy of the contract is a second thing to forget to
    update, and the whole point of a contract is that there is one of it.
    """
    spec = importlib.util.spec_from_file_location(
        "_site_urls", REPO_ROOT / "tests" / "test_site_urls.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.PRINTED_PATHS)


def certificate_problem(error: BaseException) -> str | None:
    """Is this failure about TLS rather than about reachability?

    httpx wraps the ssl module's error, so the chain has to be walked. Getting
    this wrong in either direction is bad: a certificate failure reported as a
    dead link sends somebody to check DNS, and a dead link reported as a
    certificate failure sends them to a certificate authority.
    """
    seen = error
    while seen is not None:
        if isinstance(seen, ssl.SSLCertVerificationError):
            return f"certificate verification failed: {seen.verify_message or seen}"
        if isinstance(seen, ssl.SSLError):
            return f"TLS failure: {seen}"
        seen = seen.__cause__ or seen.__context__
    return None


def check(client: httpx.Client, path: str, expected_host: str,
          expect_hub_content: bool = False) -> Result:
    """Request one printed URL and classify what came back."""
    url = f"{SITE}{path}" if path != "/" else f"{SITE}/"
    try:
        response = client.get(url)
    except Exception as error:  # noqa: BLE001 - classified, then reported
        tls = certificate_problem(error)
        if tls:
            return Result(path, url, "CERTIFICATE", None, None, None, 0, tls)
        return Result(path, url, "UNREACHABLE", None, None, None, 0,
                      f"{type(error).__name__}: {error}")

    final_url = str(response.url)
    final_host = urlparse(final_url).netloc
    hops = len(response.history)

    if response.status_code != 200:
        return Result(path, url, "STATUS", response.status_code, final_url,
                      final_host, hops,
                      f"final status {response.status_code}, expected 200")

    if final_host != expected_host:
        return Result(path, url, "HOST", response.status_code, final_url,
                      final_host, hops,
                      f"landed on {final_host}, expected {expected_host}")

    if expect_hub_content and HUB_MARKER not in response.text:
        return Result(path, url, "CONTENT", response.status_code, final_url,
                      final_host, hops,
                      "reached the right host with a 200 but the page served "
                      "is not the hub")

    return Result(path, url, "OK", response.status_code, final_url, final_host,
                  hops, "resolved, valid certificate, 200")


def render(results: list[Result], unprinted: list[Result]) -> str:
    lines = ["# Printed URL verification", ""]
    lines.append(f"Checked {len(results)} printed URLs and "
                 f"{len(unprinted)} that the book never prints, against the "
                 f"live site at {SITE}.")
    lines.append("")

    failed = [r for r in results + unprinted if not r.ok]
    counts: dict[str, int] = {}
    for result in results + unprinted:
        counts[result.status] = counts.get(result.status, 0) + 1
    for status in sorted(counts):
        lines.append(f"- {status}: {counts[status]}")
    lines.append("")

    lines.append("## The thirteen printed URLs")
    lines.append("")
    lines.append("| Printed | Status | HTTP | Hops | Landed on |")
    lines.append("|---|---|---|---|---|")
    for result in results:
        lines.append(
            f"| `{result.path}` | {result.status} | "
            f"{result.http_status or '-'} | {result.redirects} | "
            f"{result.final_url or '-'} |"
        )
    lines.append("")

    lines.append("## Paths the book never prints")
    lines.append("")
    lines.append("A reader who mistypes one character should not dead-end.")
    lines.append("")
    lines.append("| Path | Status | HTTP | Landed on |")
    lines.append("|---|---|---|---|")
    for result in unprinted:
        lines.append(
            f"| `{result.path}` | {result.status} | "
            f"{result.http_status or '-'} | {result.final_url or '-'} |"
        )
    lines.append("")

    if failed:
        lines.append("## Failures, which block a print run")
        lines.append("")
        for result in failed:
            lines.append(f"**{result.path}** ({result.status})")
            lines.append(f"  requested: {result.requested}")
            if result.final_url:
                lines.append(f"  landed:    {result.final_url}")
            lines.append(f"  note:      {result.note}")
            lines.append("")
    else:
        lines.append("Every printed URL resolves over HTTPS with a valid "
                     "certificate and returns 200.")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    paths = printed_paths()
    results: list[Result] = []
    unprinted: list[Result] = []

    # verify defaults to True and is never touched. A tool that can be talked
    # out of checking the certificate is a tool that eventually is.
    with httpx.Client(follow_redirects=True, timeout=TIMEOUT,
                      headers={"User-Agent": "agentic-lab-urlcheck"}) as client:
        for path in paths:
            expected = HUB_HOST if path == "/" else CODE_HOST
            print(f"  {path}")
            results.append(check(client, path, expected,
                                 expect_hub_content=(path == "/")))
        for path in NEVER_PRINTED:
            print(f"  {path} (never printed)")
            unprinted.append(check(client, path, HUB_HOST,
                                   expect_hub_content=True))

    report = render(results, unprinted)
    # Deliberately not written into site/. That is Netlify's publish
    # directory, so anything left there is served from the book's own domain,
    # and an internal check of the book's URLs has no business being one of
    # them. These two files are also gitignored: a report about what was live
    # at one moment goes stale immediately, and a committed one would have the
    # repository asserting something it cannot know is still true.
    out = REPO_ROOT / "printed_urls_report.md"
    out.write_text(report, encoding="utf-8", newline="\n")
    (REPO_ROOT / "printed_urls_report.json").write_text(
        json.dumps([asdict(r) for r in results + unprinted], indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    print()
    print(report)

    bad = [r for r in results + unprinted if not r.ok]
    if bad:
        print(f"{len(bad)} printed URL(s) failed. Nothing goes to print until "
              "this is clean.")
        return 1
    print("Every printed URL is live, valid and correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
