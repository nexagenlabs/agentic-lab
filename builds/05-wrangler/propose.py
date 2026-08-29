"""The one place a model is involved, and the smallest place it could be.

The agent sees fifteen lines and a shape summary. It never sees the file. It
proposes a mapping, which is a statement about what columns mean, and it is
wrong about that often enough to need a human signature and never trusted
about anything else.

It is not asked to convert a unit, total a column, count a row or decide
whether a value is plausible. Every one of those is arithmetic, and arithmetic
belongs in Python. What the model is good at is reading a header cell that
says "Conc (uM)" and knowing that this is a concentration in micromolar, which
is a judgement no regular expression makes reliably across instruments.

The proposal comes back unapproved. ``approved_at`` is None until a person
sets it, and ``apply_mapping`` refuses to run without it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from profile import profile
from typing import Any

from models import FileMapping

# What the model is allowed to see. Fifteen lines caps cost, caps context
# growth, and stops the model forming opinions about values.
HEAD_LINES = 15


def build_proposal_task(path: Path) -> str:
    """The prompt, built from the bounded profile and nothing else."""
    seen = profile(path)
    head = "\n".join(seen["head"][:HEAD_LINES])
    return f"""You are proposing a column mapping for an instrument export.

You can see the first {HEAD_LINES} lines and a shape summary. You cannot see
the rest of the file and you will not be shown it.

FILE: {seen["filename"]}
LINES IN FILE: {seen["n_lines"]}
DELIMITER GUESS: {seen["delimiter_guess"] or "none, the sniffer gave up"}

FIRST LINES
{head}

WHAT TO PROPOSE

For each column, give the source column name, the target column name, the unit
you believe applies, and where you saw that unit. Units belong in the target
name: conc_nM, never conc.

unit_evidence is not optional and it is not a claim. Quote the text you read
it from and say which line. If you did not read the unit anywhere and are
inferring it from the shape of the values, say INFERRED in the evidence and
set confidence to low. A unit you inferred and reported as read is the single
most expensive mistake available to you here.

Do not convert anything. Do not total anything. Do not comment on whether the
values look reasonable. Propose what the columns mean and stop.

Reply with one JSON object matching FileMapping, with approved_by and
approved_at both null. A human sets those, not you."""


def propose_mapping(path: str | Path, client: Any, model: str) -> FileMapping:
    """Ask for a mapping proposal. It comes back unapproved by construction."""
    path = Path(path)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": build_proposal_task(path)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    body = json.loads(text)

    # Whatever the model said about approval, it is not approved. A model
    # cannot sign off its own proposal, and the refusal in apply_mapping is
    # only as good as this line.
    body["approved_by"] = None
    body["approved_at"] = None
    return FileMapping(**body)


# "not inferred" contains "inferred", so a substring test reads the evidence
# backwards and flags the columns that were most carefully documented. The
# lookbehind is the whole point of this expression.
INFERRED_RE = re.compile(r"(?<!not )\binferred\b", re.IGNORECASE)


def is_inferred(evidence: str) -> bool:
    """Whether this evidence says the unit was inferred rather than read."""
    return bool(INFERRED_RE.search(evidence or ""))


def unit_evidence_problems(mapping: FileMapping) -> list[str]:
    """Which mapped columns claim a unit without saying where it came from.

    A claim is not evidence. This is checkable precisely because the agent was
    told to quote the text, so a proposal that asserts nanomolar with nothing
    behind it can be sent back rather than signed.
    """
    problems = []
    for column in mapping.columns:
        evidence = (column.unit_evidence or "").strip()
        if not evidence:
            problems.append(f"{column.source_column}: no unit_evidence at all")
            continue
        if column.detected_unit and not is_inferred(evidence):
            quoted = any(token in evidence for token in ("line", "header", "row"))
            if not quoted:
                problems.append(
                    f"{column.source_column}: claims unit "
                    f"{column.detected_unit!r} without saying where it was read"
                )
        if is_inferred(evidence) and column.confidence != "low":
            problems.append(
                f"{column.source_column}: inferred the unit but did not mark "
                "the confidence low"
            )
    return problems
