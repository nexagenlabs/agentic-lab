"""Offline stand-in for the client. No test may reach the network.

The proposal step is the only place a model appears in this build, so this is
the only stub it needs. It replays a canned proposal and records the prompt it
was given, which is what lets a test assert the model was shown fifteen lines
and not the file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class Usage:
    input_tokens: int = 900
    output_tokens: int = 300


@dataclass
class StubResponse:
    model: str
    stop_reason: str
    content: list[Any]
    usage: Usage


PROPOSAL = {
    "instrument": "qpcr_long",
    "layout": "long",
    "header_row": 0,
    "approved_by": None,
    "approved_at": None,
    "columns": [
        {"source_column": "Plate", "target_column": "plate_id",
         "detected_unit": None,
         "unit_evidence": "Read from the file: header cell Plate, line 1.",
         "confidence": "high"},
        {"source_column": "Well", "target_column": "well",
         "detected_unit": None,
         "unit_evidence": "Read from the file: header cell Well, line 1.",
         "confidence": "high"},
        {"source_column": "Compound", "target_column": "compound",
         "detected_unit": None,
         "unit_evidence": "Read from the file: header cell Compound, line 1.",
         "confidence": "high"},
        {"source_column": "Conc (uM)", "target_column": "conc",
         "detected_unit": "uM",
         "unit_evidence": "Read from the file: the unit is in the header cell "
                          "itself, Conc (uM), on line 1.",
         "confidence": "high"},
        {"source_column": "Rep", "target_column": "replicate",
         "detected_unit": None,
         "unit_evidence": "Read from the file: header cell Rep, line 1.",
         "confidence": "high"},
        {"source_column": "Signal", "target_column": "viability",
         "detected_unit": None,
         "unit_evidence": "INFERRED, not read. The header says Signal and "
                          "gives no unit.",
         "confidence": "low"},
    ],
}

# A proposal that asserts a unit with nothing behind it. Used to prove the
# evidence check is a check rather than a formality.
UNSUPPORTED_PROPOSAL = json.loads(json.dumps(PROPOSAL))
UNSUPPORTED_PROPOSAL["columns"][3]["unit_evidence"] = "It is micromolar."


@dataclass
class StubMessages:
    payload: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> StubResponse:
        self.calls.append(kwargs)
        block = TextBlock(text=json.dumps(self.payload))
        return StubResponse("stub-wrangler-1", "end_turn", [block], Usage())

    @property
    def last_prompt(self) -> str:
        return self.calls[-1]["messages"][0]["content"]


class StubClient:
    """Returns a canned mapping proposal and remembers what it was asked."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.messages = StubMessages(payload or PROPOSAL)
