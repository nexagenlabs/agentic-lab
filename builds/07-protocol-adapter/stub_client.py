"""Offline stand-in for the client. No test may reach the network.

Extraction is the only place a model appears in this build, so this is the
only stub it needs. It keys off the DOI in the prompt and replays a recorded
reading of that protocol.

The reading for ``ambiguous_density`` is the interesting one. It is written to
do exactly what a model does when a methods section will not tell it what it
was asked for: it answers 5000 cells per well, quotes the sentence it read
honestly, and the sentence does not contain 5000. Nothing in this file cheats
to make the build look good. If ``verify`` stopped working, that stub would
sail through and the adaptation would carry an invented number.
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
    input_tokens: int = 700
    output_tokens: int = 400


@dataclass
class StubResponse:
    model: str
    stop_reason: str
    content: list[Any]
    usage: Usage


def _stated(parameter: str, value: str, evidence: str) -> dict[str, Any]:
    return {"parameter": parameter, "stated": True, "value": value,
            "evidence": evidence}


def _silent(parameter: str) -> dict[str, Any]:
    return {"parameter": parameter, "stated": False, "value": None,
            "evidence": None}


READINGS: dict[str, list[dict[str, Any]]] = {
    # Every parameter stated, every quote real, every number in its quote.
    "10.5555/agenticlab.2026.00711": [
        _stated("seeding_density", "3000 cells per well",
                "Cells were seeded at 3000 cells per well in 96-well plates"),
        _stated("incubation_to_endpoint", "72 h",
                "Viability was measured 72 h after treatment"),
        _stated("solvent_tolerance", "0.5 % DMSO",
                "the final vehicle concentration did not exceed 0.5 % in any "
                "well"),
        _stated("passage_number_range", "passage 4 to passage 18",
                "Cells were used between passage 4 and passage 18"),
        _stated("serum_concentration", "10 %",
                "supplemented with 10 % foetal bovine serum"),
        _stated("readout_chemistry", "resazurin reduction",
                "using a resazurin reduction assay"),
    ],
    # Two parameters the paper simply does not mention. The model says so.
    "10.5555/agenticlab.2026.00712": [
        _silent("seeding_density"),
        _silent("incubation_to_endpoint"),
        _stated("solvent_tolerance", "0.5 % DMSO",
                "the final solvent concentration did not exceed 0.5 %"),
        _stated("passage_number_range", "passage 5 to passage 15",
                "maintained between passage 5 and passage 15"),
        _stated("serum_concentration", "10 %",
                "DMEM with 10 % foetal bovine serum"),
        _stated("readout_chemistry", "ATP luminescence",
                "Viability was determined by ATP luminescence"),
    ],
    # The one that invents. Both quotes are verbatim from the protocol and
    # neither supports the value reported against it.
    "10.5555/agenticlab.2026.00713": [
        _stated("seeding_density", "5000 cells per well",
                "Cells were seeded at an appropriate density in 96-well "
                "plates"),
        _stated("incubation_to_endpoint", "48 h",
                "A resazurin reduction assay was read 48 h after treatment"),
        _stated("solvent_tolerance", "0.5 % DMSO",
                "DMSO was kept below 0.5 % in all conditions"),
        _stated("passage_number_range", "passage 3 to passage 10",
                "Low passage cultures were used throughout"),
        _stated("serum_concentration", "10 %",
                "DMEM containing 10 % foetal bovine serum"),
        _stated("readout_chemistry", "resazurin reduction",
                "A resazurin reduction assay was read 48 h after treatment"),
    ],
}


@dataclass
class StubMessages:
    prompts: list[str] = field(default_factory=list)

    def create(self, **kwargs: Any) -> StubResponse:
        prompt = kwargs["messages"][-1]["content"]
        self.prompts.append(prompt)

        for doi, reading in READINGS.items():
            # The protocol body is in the prompt, so the stub finds itself the
            # same way a reader would: by looking for something only that
            # protocol says.
            if _fingerprint(doi) in prompt:
                payload = {"parameters": reading}
                break
        else:
            raise AssertionError(
                "the stub has no recorded reading for this prompt; add one "
                "rather than letting a test reach for the network"
            )

        return StubResponse(
            model=kwargs.get("model", "stub"),
            stop_reason="end_turn",
            content=[TextBlock(text=json.dumps(payload))],
            usage=Usage(),
        )


# A sentence unique to each protocol, since the prompt carries the body rather
# than the front matter the DOI lives in.
FINGERPRINTS = {
    "10.5555/agenticlab.2026.00711": "Cells were seeded at 3000 cells per well",
    "10.5555/agenticlab.2026.00712": "Viability was determined by ATP luminescence",
    "10.5555/agenticlab.2026.00713": "Cells were seeded at an appropriate density",
}


def _fingerprint(doi: str) -> str:
    return FINGERPRINTS[doi]


@dataclass
class StubClient:
    """Shaped like the real client, and it answers from a recording."""

    messages: StubMessages = field(default_factory=StubMessages)

    @property
    def prompts(self) -> list[str]:
        return self.messages.prompts
