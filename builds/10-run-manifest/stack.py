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

from pipeline import BATCH_SIZE

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

BUILD = "10-run-manifest"
CHAPTER = 9

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        UNSPECIFIED,
        "screen() takes its client from the caller, so this build names no "
        "model. The manifest records the model that answered, with its "
        "version, temperature and seed, which is the stronger record: it "
        "names what ran rather than what was configured.",
    ),
    "tools": row(
        "none: one enrichment call per batch and one verdict per record, both "
        "made by code",
        "every number in the outputs is counted in Python from the model's "
        "own words.",
    ),
    "working_memory": row(
        f"one batch of {BATCH_SIZE} records at a time",
        "nothing is carried between batches except the trace.",
    ),
    "episodic_memory": row(
        "the run manifest, the trace and the outputs, each addressed by "
        "content hash",
        "this is the build. A manifest recording provenance nobody verifies "
        "is decorative, which is why the replay checks the input hashes.",
    ),
    "reference_memory": row(
        "the criteria file and the corpus, recorded as inputs with their "
        "hashes and their retrieval times",
        "plus the corpus snapshot id, so a replay that disagrees can say "
        "which version of the world it operated on.",
    ),
    "orchestration": row(
        "chain, one model verdict per record. The replay path makes no model "
        "call at all.",
        "the deterministic half produces the outputs from the model's own "
        "words, which is what makes an offline replay possible.",
    ),
    "trace": row(
        "JSONL, with its path and its hash both recorded in the manifest",
        "a trace nobody hashed is a trace somebody can edit.",
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
