"""Chapter 2's Stack Inventory for this build, derived from the code beside it.

Seven questions, answered from the modules in this folder rather than from
memory, so an answer that stops being true stops being emitted. A question this
build does not settle is emitted as UNSPECIFIED rather than left out. An absent
row reads as a system with nothing in that position; an unanswered row means
nobody decided, and Chapter 2's argument is that a step nobody decided is not a
default but an unbounded loop with your API key attached.

Copied into every build rather than imported from one place, for the reason
tracing.py is copied: a reader who opens this folder alone must find everything
it needs inside it. tests/test_stack_inventory.py holds the twelve copies to
the same seven questions as templates/stack.yaml.

Run it:

    python stack.py        # rewrites stack.yaml beside this file
"""

from __future__ import annotations

import json
from pathlib import Path

from checks import MIN_RELIABLE_UL
from synergy import MODELS

# Word for word from templates/stack.yaml, and a test says so.
QUESTIONS: dict[str, str] = {
    "model":
        "Which model answers, at which version, and where is that name configured?",
    "tools":
        "What can it call, and what can each of those reach?",
    "working_memory":
        "What does the loop carry from one step to the next, and what bounds it?",
    "episodic_memory":
        "What survives after the run ends, and who can read it back?",
    "reference_memory":
        "What does it consult that it cannot change?",
    "orchestration":
        "What decides the next step: the model, or the code?",
    "trace":
        "Where does the record of the run go, and what does it hold?",
}

UNSPECIFIED = "UNSPECIFIED"


def row(value: str, note: str = "") -> tuple[str, str]:
    """One answered row. A call rather than a tuple literal, because ruff
    reads an implicit string concatenation inside a collection as a missing
    comma, and it is usually right."""
    return value, note

BUILD = "06-plate-mapper"
CHAPTER = 6

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        "none: this build makes no model call",
        "the arithmetic a plate layout depends on is not a thing to ask a "
        "model for.",
    ),
    "tools": row(
        "none: nothing is offered to a model, because there is no model",
        "",
    ),
    "working_memory": row(
        "none: there is no loop and no conversation",
        "",
    ),
    "episodic_memory": row(
        "the committed design file in designs/, including its synergy model "
        "commitment and the timestamp on it",
        "the commitment has to predate the data, which is the whole point of "
        "writing it down.",
    ),
    "reference_memory": row(
        f"the dilution and geometry rules in checks.py, including a "
        f"{MIN_RELIABLE_UL} uL minimum reliable transfer, and the "
        f"{len(MODELS)} synergy models a design may commit to",
        "",
    ),
    "orchestration": row(
        "script: a design is validated, or it is refused with the check that "
        "refused it",
        "",
    ),
    "trace": row(
        UNSPECIFIED,
        "this build writes no trace of its own. It is called by other code, "
        "and the run that matters is the caller's, which is where Build 10 "
        "and Build 12 record it. Worth deciding rather than inheriting.",
    ),
}


def as_yaml() -> str:
    """The inventory as YAML, in the order Chapter 2 asks the questions."""
    lines = [
        f"# Stack inventory for Build {BUILD}, emitted by stack.py.",
        "# Chapter 2 of The Agentic Lab. Regenerate rather than edit.",
        f"build: {json.dumps(BUILD)}",
        f"chapter: {CHAPTER}",
        "stack_inventory:",
    ]
    for field, question in QUESTIONS.items():
        value, note = INVENTORY[field]
        lines += [
            f"  {field}:",
            f"    question: {json.dumps(question)}",
            f"    value: {json.dumps(value)}",
            f"    note: {json.dumps(note)}",
        ]
    return "\n".join(lines) + "\n"


def write(path: str | Path | None = None) -> Path:
    """Emit the inventory beside this file, or wherever the caller says."""
    target = Path(path) if path else Path(__file__).resolve().parent / "stack.yaml"
    target.write_text(as_yaml(), encoding="utf-8", newline="\n")
    return target


if __name__ == "__main__":
    print(write())
