"""Disagreements, laid out for a person. Nothing here resolves anything.

There is deliberately no tie-break rule, no confidence comparison, no majority
of two, and no third screen brought in to break the deadlock. Every one of
those would turn a disagreement into a verdict without anyone having read the
record, which is the failure the two-reviewer standard exists to prevent.

The count that comes out of here is the honest cost of the screen. A pair of
screens that sends four hundred records to adjudication has not saved anybody
anything, and that fact should be visible in the output rather than discovered
three weeks later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models import Verdict

UNRESOLVED = None

RESOLUTION_NOTE = (
    "Every record below is unresolved. No rule in this build breaks a tie: "
    "not confidence, not seniority of model, not a third screen. A human "
    "reads the record and decides, and records the decision in the "
    "resolution field. A disagreement resolved automatically is a verdict "
    "nobody made."
)


@dataclass(frozen=True)
class Disagreement:
    """One record the two screens read differently."""

    pmid: str
    a_decision: str
    a_reason: str
    a_confidence: str
    b_decision: str
    b_reason: str
    b_confidence: str
    resolution: Any = UNRESOLVED

    def as_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "screen_a": {
                "decision": self.a_decision,
                "reason": self.a_reason,
                "confidence": self.a_confidence,
            },
            "screen_b": {
                "decision": self.b_decision,
                "reason": self.b_reason,
                "confidence": self.b_confidence,
            },
            "resolution": self.resolution,
        }


@dataclass
class Adjudication:
    """The whole set of disagreements, and what it cost."""

    disagreements: tuple[Disagreement, ...] = field(default_factory=tuple)
    compared: int = 0

    @property
    def count(self) -> int:
        return len(self.disagreements)

    @property
    def share(self) -> float:
        return self.count / self.compared if self.compared else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "note": RESOLUTION_NOTE,
            "records_compared": self.compared,
            "sent_to_human_adjudication": self.count,
            "share_of_corpus": self.share,
            "all_unresolved": all(d.resolution is UNRESOLVED for d in self.disagreements),
            "disagreements": [d.as_dict() for d in self.disagreements],
        }


def _by_pmid(verdicts: list[Verdict]) -> dict[str, Verdict]:
    return {v.pmid: v for v in verdicts}


def find_disagreements(
    verdicts_a: list[Verdict], verdicts_b: list[Verdict]
) -> Adjudication:
    """Every record on which the two screens differ, with both reasons.

    Both reasons travel together. A disagreement stripped of its reasons is a
    row in a table that a human cannot act on without opening two other files.
    """
    a = _by_pmid(verdicts_a)
    b = _by_pmid(verdicts_b)
    shared = sorted(set(a) & set(b))

    found = tuple(
        Disagreement(
            pmid=pmid,
            a_decision=a[pmid].decision,
            a_reason=a[pmid].reason,
            a_confidence=a[pmid].confidence,
            b_decision=b[pmid].decision,
            b_reason=b[pmid].reason,
            b_confidence=b[pmid].confidence,
        )
        for pmid in shared
        if a[pmid].decision != b[pmid].decision
    )
    return Adjudication(found, len(shared))


def write_adjudication(path: str | Path, adjudication: Adjudication) -> Path:
    """Write the adjudication file a person will work through."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(adjudication.as_dict(), indent=2) + "\n", encoding="utf-8")
    return path
