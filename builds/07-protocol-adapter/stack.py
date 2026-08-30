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

from adapt import DEFAULT_LINES
from config import AGENT_MODEL
from models import MANDATORY_PARAMETERS

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

BUILD = "07-protocol-adapter"
CHAPTER = 6

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        AGENT_MODEL,
        "AGENT_MODEL, defaulted in config.py.",
    ),
    "tools": row(
        "none: the model is asked to extract parameters from one protocol and "
        "calls nothing",
        "every number it returns is checked against the source text before it "
        "is used, and a number the source never stated is named rather than "
        "filled in.",
    ),
    "working_memory": row(
        "one protocol at a time: the source text and the extraction task",
        "nothing from an earlier protocol is carried in.",
    ),
    "episodic_memory": row(
        "the adapted protocol and its diff, written by the caller",
        "the diff is the product: what changed, what was carried over, and "
        "what the source never stated.",
    ),
    "reference_memory": row(
        f"{DEFAULT_LINES.name}, the cell line facts an adaptation is checked "
        f"against, and the {len(MANDATORY_PARAMETERS)} mandatory parameters "
        f"in models.py",
        "",
    ),
    "orchestration": row(
        "chain: extract, verify in code, then diff",
        "the model proposes and Python disposes.",
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
