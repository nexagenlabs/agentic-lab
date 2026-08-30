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

from adapters import WORKER_TIMEOUT_S
from families import known_families

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

BUILD = "11-red-team"
CHAPTER = 10

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        "none: the harness calls no model",
        "it runs the earlier builds' code in subprocesses and counts what "
        "their checks catch. A model here would be a second thing to debug.",
    ),
    "tools": row(
        "none",
        "",
    ),
    "working_memory": row(
        "none: each fault is one job to one worker, and no worker sees "
        "another's result",
        "",
    ),
    "episodic_memory": row(
        "the red team run manifest: what was planted, what was caught, what "
        "was missed, and what was missed silently",
        "the silent misses are the number that matters. A fault that fails "
        "loudly is a fault somebody notices.",
    ),
    "reference_memory": row(
        f"catalogue.py, the fault definitions across {len(known_families())} "
        f"families, and the earlier builds' own fixtures",
        "the faults are declared with the check that should catch each one, "
        "so a miss names the check that did not fire.",
    ),
    "orchestration": row(
        f"script: one subprocess worker per build, {WORKER_TIMEOUT_S} seconds "
        f"each, jobs on stdin and results on stdout",
        "a subprocess rather than an import, because eleven builds share "
        "module names and importing them into one process would measure the "
        "wrong code.",
    ),
    "trace": row(
        "the run manifest, written as JSON",
        "no JSONL trace of its own: the trace that matters is the one each "
        "worker's build writes.",
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
