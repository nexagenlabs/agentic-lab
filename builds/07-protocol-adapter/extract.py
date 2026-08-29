"""The one place a model is involved, and the smallest place it could be.

Reading "cells were seeded at 3000 cells per well" out of a methods section is
a language problem and a model is good at it. Deciding what 3000 becomes in a
line that doubles half as fast is arithmetic, and arithmetic belongs in
Python. So this module asks one question and asks nothing else: for each of
the six parameters, does the source state it, and which sentence says so.

Everything the model returns then goes through ``verify``, which is where the
build stops it inventing. Two conditions, both mechanical:

  the quoted evidence must appear in the protocol text, and
  every number in the reported value must appear in that quote.

The second is the one that earns its keep. A model asked for a seeding density
and shown "cells were seeded at an appropriate density in 96-well plates" will
sometimes answer 5000, because 5000 is what everybody uses, and it will quote
the sentence honestly while doing it. Testing that the quote merely contains a
digit is not enough, because that sentence contains 96. Testing that the quote
contains 5000 is enough, and no wording of the prompt is as reliable.
"""

from __future__ import annotations

import json
import re
from typing import Any

from models import MANDATORY_PARAMETERS, ExtractedParameter
from source import SourceProtocol

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Readout chemistry is the one Table 6.2 parameter that is not a quantity, so
# it is the one exception. Everything else is a number or a range, and a claim
# about one that no number in the quote supports is not a reading.
NON_QUANTITATIVE = frozenset({"readout_chemistry"})


def build_extraction_task(protocol: SourceProtocol) -> str:
    """The prompt. It asks for readings, not for judgements."""
    parameters = "\n".join(f"  - {name}" for name in MANDATORY_PARAMETERS)
    schema = ('{"parameters": [{"parameter": ..., "stated": true or false, '
              '"value": string or null, "evidence": string or null}]}')
    return f"""You are reading the methods section of a published protocol.

Report, for each parameter below, whether this protocol states it and which
sentence says so.

PARAMETERS
{parameters}

PROTOCOL
{protocol.body.strip()}

RULES

Quote evidence verbatim from the text above. Do not paraphrase it and do not
assemble it from two places.

If the protocol does not state a parameter, say so. If it gestures at one
without giving a value, for example "an appropriate density" or "low passage",
that is not a statement of the parameter: set stated to false. A typical value
from your own experience is not a reading of this protocol, and reporting one
here is the single most expensive mistake available to you.

Do not convert units, do not adapt anything to another cell line and do not
comment on whether the values are sensible. Report what the text says and stop.

Reply with one JSON object of the form {schema}"""


def extract_parameters(
    protocol: SourceProtocol, client: Any, model: str
) -> list[ExtractedParameter]:
    """Ask what the protocol states. Nothing that comes back is trusted yet."""
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": build_extraction_task(protocol)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    body = json.loads(text)

    returned = {item["parameter"]: item for item in body.get("parameters", [])}
    out = []
    for name in MANDATORY_PARAMETERS:
        item = returned.get(name, {})
        out.append(ExtractedParameter(
            parameter=name,
            stated=bool(item.get("stated")),
            value=item.get("value"),
            evidence=item.get("evidence"),
        ))
    return out


def _unsupported_numbers(value: str, evidence: str) -> list[str]:
    """Numbers claimed in the value that the quoted sentence does not carry."""
    return [n for n in NUMBER_RE.findall(value) if n not in evidence]


def _rejection_code(
    protocol: SourceProtocol, item: ExtractedParameter
) -> str | None:
    """Why this claim does not stand, or None if it does."""
    if not item.evidence:
        return "no_evidence"
    if not protocol.quotes(item.evidence):
        return "evidence_not_in_source"
    if item.parameter in NON_QUANTITATIVE:
        return None
    if not item.value or not NUMBER_RE.search(item.value):
        return "value_carries_no_quantity"
    if _unsupported_numbers(item.value, item.evidence):
        return "value_not_supported_by_evidence"
    return None


def verify(
    protocol: SourceProtocol, extracted: list[ExtractedParameter]
) -> tuple[list[ExtractedParameter], list[dict[str, str]]]:
    """Demote every claim the protocol does not actually support.

    Returns the verified readings and a list of rejections, each carrying a
    code, so the trace records what the model claimed and why it did not stand
    rather than losing it.
    """
    verified: list[ExtractedParameter] = []
    rejected: list[dict[str, str]] = []

    for item in extracted:
        if not item.stated:
            verified.append(item)
            continue

        code = _rejection_code(protocol, item)
        if code is None:
            verified.append(item)
            continue

        rejected.append({
            "status": "REJECTED",
            "code": code,
            "parameter": item.parameter,
            "claimed_value": str(item.value),
            "evidence": str(item.evidence),
        })
        # Demoted, not deleted. The parameter is now unstated, which is what
        # the protocol actually says, and the claim survives in the trace.
        verified.append(ExtractedParameter(
            parameter=item.parameter, stated=False, value=None,
            evidence=item.evidence,
        ))

    return verified, rejected
