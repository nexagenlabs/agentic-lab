"""Citation checking is existence checking. Everything else is theatre.

A fabricated reference characteristically pairs a real journal with a
nonexistent title, real-looking author names with a plausible year, and a DOI
that is either syntactically perfect and unregistered or registered to a
different paper entirely. Every one of those passes a check that asks whether a
citation *looks* right, because looking right is the thing they are good at.

So there is exactly one question worth asking, and it has to be asked of
something outside the model: does this identifier resolve, and does what comes
back say what the citation claims it says? Three checks fall out of that, and
the third is the one people leave out:

``citation_exists``
    the identifier resolves to nothing at all

``citation_metadata_matches``
    it resolves, and the title, authors or year disagree with the claim

``citation_quote_supported``
    it resolves, the metadata agrees, and the finding attributed to it is not
    in the record. This is the expensive one to check and the easy one to
    fabricate, because by this point everything verifiable has verified.

The source sits behind a protocol with a fixture-backed stub, the same
arrangement Build 08 uses for Vina. ``StubMetadataSource`` is what the gate
runs. ``HttpMetadataSource`` is the shape a real one takes and nothing in the
gate calls it, because a test that needs Crossref is a test that fails on a
train and then gets deleted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict


def normalise(text: str) -> str:
    """Compare titles the way a librarian would, not the way bytes do."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def surname(author: str) -> str:
    return normalise(author.split(",")[0].split()[-1] if author.strip() else "")


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_id: str
    title: str
    authors: list[str]
    year: int
    journal: str
    doi: str | None = None
    pmid: str | None = None
    # What the citing text claims this reference says. Optional, because not
    # every citation makes a claim; where one does, it is checkable.
    quoted_finding: str | None = None

    @property
    def identifier(self) -> str:
        return self.doi or self.pmid or self.ref_id


class CitationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_id: str
    checks_fired: list[str]
    detail: str

    @property
    def resolves(self) -> bool:
        return "citation_exists" not in self.checks_fired

    @property
    def clean(self) -> bool:
        return not self.checks_fired


class MetadataSource(Protocol):
    def lookup(self, identifier: str) -> dict[str, Any] | None: ...


class StubMetadataSource:
    """A metadata index backed by a committed fixture.

    It answers for the identifiers it knows and returns None for everything
    else, which is exactly what a real index does for a DOI that was never
    registered. The fixture is the world; a fabricated reference is one that
    is not in it.
    """

    def __init__(self, path: str | Path) -> None:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
        self.records: dict[str, dict[str, Any]] = body["records"]
        self.lookups: list[str] = []

    def lookup(self, identifier: str) -> dict[str, Any] | None:
        self.lookups.append(identifier)
        return self.records.get(identifier)


class HttpMetadataSource:
    """The shape a real source takes. Nothing in the gate calls this."""

    def __init__(self, base_url: str = "https://api.crossref.org/works",
                 client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    def lookup(self, identifier: str) -> dict[str, Any] | None:
        client = self._client or httpx.Client(timeout=20.0)
        response = client.get(f"{self.base_url}/{identifier}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("message")


def check_reference(reference: Reference,
                    source: MetadataSource) -> CitationFinding:
    """Resolve it, then compare what came back against what was claimed."""
    record = source.lookup(reference.identifier)
    if record is None:
        return CitationFinding(
            ref_id=reference.ref_id,
            checks_fired=["citation_exists"],
            detail=(f"{reference.identifier} resolves to nothing. The journal "
                    f"{reference.journal!r} is real and the title is not."),
        )

    fired, notes = [], []
    if normalise(record["title"]) != normalise(reference.title):
        fired.append("citation_metadata_matches")
        notes.append(f"title is {record['title']!r}, not {reference.title!r}")
    if int(record["year"]) != int(reference.year):
        fired.append("citation_metadata_matches")
        notes.append(f"year is {record['year']}, not {reference.year}")

    claimed = {surname(name) for name in reference.authors}
    actual = {surname(name) for name in record.get("authors", [])}
    if claimed and actual and not (claimed & actual):
        fired.append("citation_metadata_matches")
        notes.append(f"no author in common: {sorted(claimed)} against "
                     f"{sorted(actual)}")

    if reference.quoted_finding:
        supported = any(
            normalise(reference.quoted_finding) in normalise(finding)
            or normalise(finding) in normalise(reference.quoted_finding)
            for finding in record.get("findings", [])
        )
        if not supported:
            fired.append("citation_quote_supported")
            notes.append(
                f"the record does not contain {reference.quoted_finding!r}. "
                "Everything verifiable about this reference verified, which "
                "is what makes this the expensive one."
            )

    return CitationFinding(
        ref_id=reference.ref_id,
        # Sorted and de-duplicated, so three metadata disagreements are one
        # check firing rather than three.
        checks_fired=sorted(set(fired)),
        detail="; ".join(notes) or "resolves, and agrees with what was claimed",
    )


def check_all(references: list[dict[str, Any]],
              source: MetadataSource) -> tuple[list[str], list[CitationFinding]]:
    """Every reference in a payload, with the checks that fired across them."""
    findings = [check_reference(Reference(**body), source) for body in references]
    fired = sorted({name for finding in findings for name in finding.checks_fired})
    return fired, findings
