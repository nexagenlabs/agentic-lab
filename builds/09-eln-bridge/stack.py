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

from config import MODEL, MODEL_VERSION
from gate import SCREENFUL

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

BUILD = "09-eln-bridge"
CHAPTER = 8

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        f"{MODEL}, version {MODEL_VERSION}",
        "AGENT_MODEL and AGENT_MODEL_VERSION, config.py. Both travel with "
        "every entry as machine attribution, because an entry nobody can "
        "attribute is an entry somebody will assume a person wrote.",
    ),
    "tools": row(
        "none: the model drafts, and every write is made by code after a "
        "person approves it",
        "there is no update and no delete anywhere in the build. The absence "
        "is the safety property.",
    ),
    "working_memory": row(
        "one record at a time: the record, the design it cites, and the draft",
        "text arriving from a record is wrapped as untrusted before the model "
        "sees it.",
    ),
    "episodic_memory": row(
        "the append-only ledger, one JSONL file per run, which the notebook "
        "cannot overwrite",
        "opened in append mode and nothing else. The ledger and the notebook "
        "are written separately so the two can be compared.",
    ),
    "reference_memory": row(
        "fixtures/designs, the design a proposal's numbers are cross-checked "
        "against",
        "a proposal citing no design is reported rather than passed.",
    ),
    "orchestration": row(
        f"chain with a human gate, batched at {SCREENFUL} proposals to a "
        f"screen: draft, cross-check, propose, approve, write twice",
        "the gate costs more to approve than to reject, deliberately.",
    ),
    "trace": row(
        "JSONL, one event per line",
        "separate from the ledger, which is the record of what was written "
        "rather than of what happened.",
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
