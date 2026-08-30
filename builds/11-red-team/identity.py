"""The fifth family: two records that are one thing.

Chapter 10 ends with a harness that scored 1.0 across thirty-one faults and was
wrong. It missed a preprint and its published version counted as two papers.
Nobody wrote a bad check. Deduplication worked on identifiers, correctly, and a
preprint and its published version have different identifiers, correctly. The
system was right at every level except the one that mattered.

That is why this file exists and why ``families.py`` keeps the family set open.
The failure was not a missing check inside a known category. It was a missing
category, and a fixed enum makes a missing category permanent.

Three checks, in the order they are cheap:

``duplicate_identifier``
    the same identifier twice. Every system already does this, which is
    exactly why it is the one that gives the false confidence.

``duplicate_normalised_title``
    the same title differing in whitespace, case or punctuation. One line of
    normalisation, almost never written.

``duplicate_work``
    two records that are the same work under different identifiers: a preprint
    and its published version, or one paper indexed under a DOI in one place
    and a PMID in another. This is the one the chapter's harness lacked, and
    it cannot be done on identifiers at all. It needs title, first author and
    a year window, and it will still miss things.

The last check is honest about being a heuristic. It matches on normalised
title plus a shared author surname, within a two-year window, because a
preprint and its published version are usually a year apart and occasionally
two. It will merge two genuinely distinct papers with the same title by the
same group, and that is a real cost, disclosed here rather than discovered.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict

# A preprint and its published version are typically months apart and
# sometimes longer. Two years is generous and will occasionally be wrong.
PUBLICATION_WINDOW_YEARS = 2

PREPRINT_SERVERS = ("biorxiv", "medrxiv", "arxiv", "chemrxiv", "researchsquare")


def normalise_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def surnames(authors: list[str]) -> set[str]:
    out = set()
    for author in authors:
        parts = re.findall(r"[A-Za-z]+", author)
        if parts:
            out.add(parts[-1].lower() if len(parts[-1]) > 1 else parts[0].lower())
    return out


class DuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str
    record_ids: list[str]
    detail: str


def find_duplicates(records: list[dict[str, Any]]) -> list[DuplicateGroup]:
    """Every group of records that are one thing, with which check found it."""
    groups: list[DuplicateGroup] = []

    by_identifier: dict[str, list[str]] = {}
    for record in records:
        identifier = str(record.get("pmid") or record.get("doi") or record["id"])
        by_identifier.setdefault(identifier, []).append(str(record["id"]))
    for identifier, ids in sorted(by_identifier.items()):
        if len(ids) > 1:
            groups.append(DuplicateGroup(
                check="duplicate_identifier", record_ids=sorted(ids),
                detail=f"{identifier} appears {len(ids)} times",
            ))

    by_title: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_title.setdefault(normalise_title(record["title"]), []).append(record)
    for title, members in sorted(by_title.items()):
        if len(members) < 2:
            continue
        ids = sorted(str(member["id"]) for member in members)
        raw = {member["title"] for member in members}
        identifiers = {str(member.get("pmid") or member.get("doi") or "")
                       for member in members}
        if len(raw) > 1 and len(identifiers) <= 1:
            groups.append(DuplicateGroup(
                check="duplicate_normalised_title", record_ids=ids,
                detail=f"same title under {len(raw)} spellings: {sorted(raw)}",
            ))
            continue
        if _is_one_work(members):
            groups.append(DuplicateGroup(
                check="duplicate_work", record_ids=ids,
                detail=_why_one_work(members),
            ))

    return groups


def _is_one_work(members: list[dict[str, Any]]) -> bool:
    """Same title, an author in common, and within the publication window."""
    years = [int(member.get("year", 0)) for member in members]
    if max(years) - min(years) > PUBLICATION_WINDOW_YEARS:
        return False
    shared = None
    for member in members:
        names = surnames(member.get("authors", []))
        shared = names if shared is None else (shared & names)
    return bool(shared)


def _why_one_work(members: list[dict[str, Any]]) -> str:
    venues = [str(member.get("journal", "")) for member in members]
    preprint = [venue for venue in venues
                if any(server in venue.lower() for server in PREPRINT_SERVERS)]
    identifiers = [str(member.get("pmid") or member.get("doi") or member["id"])
                   for member in members]
    if preprint:
        return (f"a preprint and its published version: {venues}. The "
                f"identifiers differ ({identifiers}), which is why "
                "deduplication on identifiers counts this as two papers.")
    return (f"one work under two identifier schemes: {identifiers}. Both are "
            "correct identifiers and neither system is wrong.")


def check_identity(records: list[dict[str, Any]]) -> tuple[list[str],
                                                           list[DuplicateGroup]]:
    groups = find_duplicates(records)
    return sorted({group.check for group in groups}), groups


def deduplicate_on_identifiers(records: list[dict[str, Any]]
                               ) -> tuple[list[dict[str, Any]], list[str]]:
    """What the chapter's harness did, reproduced so it can be measured.

    This is not a straw man. It is the correct implementation of the thing it
    is implementing, it is what almost every corpus pipeline does, and it
    scored 1.0 while missing the case this module exists for.
    """
    seen: set[str] = set()
    kept, fired = [], []
    for record in records:
        identifier = str(record.get("pmid") or record.get("doi") or record["id"])
        if identifier in seen:
            fired.append("duplicate_identifier")
            continue
        seen.add(identifier)
        kept.append(record)
    return kept, sorted(set(fired))
