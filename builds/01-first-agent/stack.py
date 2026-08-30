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

from agent import TOOLS, WRITE_TOOLS, run_agent
from config import MODEL

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

BUILD = "01-first-agent"
CHAPTER = 3

# The caps are default arguments rather than module constants, so they are
# read off the signature. A cap restated here would be a second copy, and the
# second copy is the one that goes stale.
_PARAMETERS = signature(run_agent).parameters
MAX_STEPS = _PARAMETERS["max_steps"].default
TOKEN_BUDGET = _PARAMETERS["token_budget"].default
TOOL_NAMES = ", ".join(tool["name"] for tool in TOOLS)

INVENTORY: dict[str, tuple[str, str]] = {
    "model": row(
        MODEL,
        "AGENT_MODEL, defaulted in config.py. The five stage files each name "
        "it once more, because a stage has to run on a machine holding only "
        "that one file.",
    ),
    "tools": row(
        TOOL_NAMES,
        f"{', '.join(sorted(WRITE_TOOLS))} writes, and is refused unless the "
        "run was started with an approval for it.",
    ),
    "working_memory": row(
        f"one messages list per run, appended every turn, bounded at "
        f"{MAX_STEPS} steps and {TOKEN_BUDGET} tokens",
        "nothing is summarised or dropped: the bound is on the run rather "
        "than on the list.",
    ),
    "episodic_memory": row(
        "none, beyond what save_note appends to notes.jsonl",
        "no run reads that file back, so nothing carries from one run into "
        "the next.",
    ),
    "reference_memory": row(
        "the stub corpus in fixtures/, which search_pubmed reads",
        "read-only: no tool in this build writes to it.",
    ),
    "orchestration": row(
        "agent loop: the model chooses the next tool each turn and the code "
        "decides whether to run it",
        "one model call per turn, and a tool is disabled after three "
        "consecutive failures.",
    ),
    "trace": row(
        "JSONL, one event per line, runs/<run_id>.jsonl",
        "written by Trace in agent.py as the run happens; run_dir is a "
        "parameter of run_agent.",
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
