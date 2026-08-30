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

from propose import HEAD_LINES

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

BUILD = "05-wrangler"
CHAPTER = 5

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        UNSPECIFIED,
        "propose_mapping takes its client and its model name from the caller, "
        "so this build names neither. Deliberate rather than forgotten: "
        "nothing here may put a model near a number.",
    ),
    "tools": row(
        "none: the model is shown a profile of the file and asked for one "
        "mapping proposal. It calls nothing.",
        "the proposal is a mapping for a person to approve, not an action.",
    ),
    "working_memory": row(
        f"{HEAD_LINES} lines of the export and a shape summary, and nothing "
        f"else",
        "a model shown ten thousand rows starts forming opinions about the "
        "values.",
    ),
    "episodic_memory": row(
        "approved mappings in mappings/, each carrying an approver and a "
        "timestamp",
        "a mapping with no approved_at is refused, so what persists is what a "
        "person signed.",
    ),
    "reference_memory": row(
        "the pandera schema in schema.py and the plate map in pipeline.py",
        "the assertions read their bounds out of the schema rather than "
        "restating them, so there is one copy of every number.",
    ),
    "orchestration": row(
        "agent once, script thereafter: one model call proposes a mapping, "
        "and every number after that is Python",
        "the unit multiplier is selected by an approved mapping, not by the "
        "model, and the approval gate is what stands between a unit guess and "
        "a silent thousandfold error.",
    ),
    "trace": row(
        "JSONL, one event per line",
        "tracing.Trace, copied rather than imported.",
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
