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

from checkpoints import CHECKPOINTS
from config import MODEL_VERSION, TIERS
from stages import PROTOCOL_STEP_CAP, TABLE_12_1, TRIAGE_STEP_CAP

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

BUILD = "12-repurposing-desk"
CHAPTER = 12

TIER_NAMES = ", ".join(f"{tier}: {name}" for tier, name in TIERS.items())
LEVELS = ", ".join(
    f"{sum(1 for stage in TABLE_12_1 if stage.level == level)} {level}"
    for level in dict.fromkeys(stage.level for stage in TABLE_12_1)
)

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        f"{TIER_NAMES}, all at version {MODEL_VERSION}",
        "three tiers and three variables. Routing by tier is the chapter's "
        "cost argument, so one name would not do: the frontier tier answers "
        "the judgement calls and the cheap tier answers the volume.",
    ),
    "tools": row(
        "none offered as tool calls: every model call goes through ask(), and "
        "the stages that use the answer are code",
        "that is what makes the audit replay possible. The trace holds what "
        "the model said, in order, with the stage that asked.",
    ),
    "working_memory": row(
        f"one stage at a time. The two agent loops are capped at "
        f"{TRIAGE_STEP_CAP} and {PROTOCOL_STEP_CAP} steps.",
        "no stage sees another's messages: each receives the previous stage's "
        "output as data.",
    ),
    "episodic_memory": row(
        f"the run manifest, its JSONL trace, and the {len(CHECKPOINTS)} "
        f"recorded approvals",
        "an approval is signed over the content it approved, so an approval "
        "for other content is refused rather than accepted.",
    ),
    "reference_memory": row(
        "five earlier builds' fixture directories, read by path and never "
        "written",
        "read by path rather than imported, because a build that imported "
        "five others would only run inside this repository.",
    ),
    "orchestration": row(
        f"{len(TABLE_12_1)} stages, Table 12.1: {LEVELS}",
        "the level of each stage is a decision recorded in the table rather "
        "than a habit. Most of the system is script.",
    ),
    "trace": row(
        "JSONL, workspace/<run_id>.jsonl, holding every model completion "
        "verbatim",
        "which is what the offline replay reads. Nothing else needs to know "
        "about replay at all.",
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
