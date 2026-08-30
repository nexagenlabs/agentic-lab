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
from inspect import signature
from pathlib import Path

from config import GOLD_NEGATIVES, GOLD_SEED, SCREEN_A_MODEL, SCREEN_B_MODEL
from dispatch import TOOLS
from screens import run_screen

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

BUILD = "04-dual-screen"
CHAPTER = 4

TOOL_NAMES = ", ".join(tool["name"] for tool in TOOLS)
# The loop is injected into run_screen rather than imported, so the cap this
# build actually runs under is that parameter's default.
MAX_STEPS = signature(run_screen).parameters["max_steps"].default

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        f"{SCREEN_A_MODEL} for screen A, {SCREEN_B_MODEL} for screen B",
        "two variables, SCREEN_A_MODEL and SCREEN_B_MODEL. Setting AGENT_MODEL "
        "alone leaves screen B where it was, which is the point: a dual screen "
        "run twice on one model is one screen run twice.",
    ),
    "tools": row(
        TOOL_NAMES,
        "the same belt for both screens. The screens differ in model and in "
        "prompt wording, not in what they can reach.",
    ),
    "working_memory": row(
        f"one messages list per record per screen, capped at {MAX_STEPS} "
        f"steps",
        "screen B never sees screen A's verdicts: run_screen has no parameter "
        "through which they could arrive. The loop is injected rather than "
        "imported, and agent.py in this folder imports a name config.py does "
        "not define, so it is not the loop this build runs.",
    ),
    "episodic_memory": row(
        "the metadata cache in cache.py, keyed by record with a digest over "
        "the payload",
        "the caller names the directory. Nothing else survives a run.",
    ),
    "reference_memory": row(
        f"criteria/repurposing_v3.yaml, and a gold set built by a stated rule "
        f"with seed {GOLD_SEED} and {GOLD_NEGATIVES} seeded negatives",
        "the rule and the seed are recorded in the report, so the set can be "
        "rebuilt rather than trusted.",
    ),
    "orchestration": row(
        "two screens over the same corpus, one model call per record each, "
        "joined only at scoring time",
        "disagreements go to a person. A third model adjudicating would be a "
        "third opinion, not a resolution.",
    ),
    "trace": row(
        "JSONL, one event per line, runs/<run_id>.jsonl",
        "beside run_manifest.json, adjudication.json and screen_report.md, "
        "written at scoring time.",
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
