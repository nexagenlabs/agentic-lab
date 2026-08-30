"""Chapter 2's Stack Inventory, checked rather than described.

The chapter says every build emits a stack.yaml and that a pytest check
validates it. This is that check, and it exists because the claim was printed
before the mechanism was written, which is the same defect the review found
four times over.

What it enforces:

  * every build emits an inventory, from its own stack.py,
  * every inventory answers all seven rows, in the chapter's order,
  * no row is silently absent, and no row is blank or null. A row nobody
    answered says UNSPECIFIED, in those letters,
  * the seven questions are word for word the ones in templates/stack.yaml,
    across twelve copies that are deliberately not imported from one place,
  * the committed file is what the build emits today, not what it emitted
    when somebody last remembered to run it.

The last of those is the one that decays without a test. An inventory is a
claim about code that keeps changing underneath it, and an inventory nobody
regenerates is a document that describes a system that used to exist.

Each build is re-emitted in a subprocess with its own folder as the working
directory. That is how a reader runs it, and it is the only way to run twelve
builds that deliberately share module names without one build's ``config``
answering for another's.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
BUILDS_ROOT = REPO / "builds"
TEMPLATE = REPO / "templates" / "stack.yaml"

BUILDS = sorted(
    path.name for path in BUILDS_ROOT.iterdir()
    if path.is_dir() and not path.name.startswith((".", "_"))
)

# The order is the chapter's, and the order is checked: an inventory that
# answers the seven questions in a different order is answering a different
# set of questions than the one the reader is holding.
FIELDS = (
    "model",
    "tools",
    "working_memory",
    "episodic_memory",
    "reference_memory",
    "orchestration",
    "trace",
)

UNSPECIFIED = "UNSPECIFIED"

# How many rows across the twelve builds nobody has settled. Anchored, because
# this is the number Chapter 2's argument is about: a row nobody decided is not
# a default. If it rises, a build stopped answering a question it used to
# answer. If it falls, somebody answered one, and this line should fall with
# it.
#
#   05-wrangler   model   the caller supplies the client and the model name
#   06-plate-mapper trace this build writes no trace of its own
#   10-run-manifest model the caller supplies the client
#
UNSPECIFIED_ROWS = 3


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def inventory_path(build: str) -> Path:
    return BUILDS_ROOT / build / "stack.yaml"


def rows_of(document: dict) -> dict:
    return document.get("stack_inventory") or {}


TEMPLATE_ROWS = rows_of(load(TEMPLATE))


def test_the_template_asks_the_seven_questions():
    """The template is the source the twelve copies are held to."""
    assert tuple(TEMPLATE_ROWS) == FIELDS, (
        f"templates/stack.yaml asks {tuple(TEMPLATE_ROWS)}, and Chapter 2's "
        f"inventory is {FIELDS}"
    )
    for field, row in TEMPLATE_ROWS.items():
        assert row["question"].endswith("?"), f"{field} carries no question"
        assert row["value"] == UNSPECIFIED, (
            f"the template's {field} row must ship as {UNSPECIFIED}: it is a "
            "form, and a form that arrives pre-answered is a form nobody reads"
        )


@pytest.mark.parametrize("build", BUILDS)
def test_every_build_emits_an_inventory(build: str):
    """Chapter 2 says every build. Twelve of twelve, or the sentence is wrong."""
    emitter = BUILDS_ROOT / build / "stack.py"
    assert emitter.exists(), (
        f"{build} has no stack.py. Chapter 2 says every build emits a stack "
        "inventory, so either this build emits one or that sentence changes."
    )
    assert inventory_path(build).exists(), (
        f"{build} has stack.py and no stack.yaml. Run `python stack.py` in "
        "that folder; the emitted file is committed so a reader has it "
        "without running anything."
    )


@pytest.mark.parametrize("build", BUILDS)
def test_the_inventory_answers_every_question(build: str):
    """All seven rows, in order, none absent, none blank."""
    document = load(inventory_path(build))
    assert document.get("build") == build, (
        f"{build}/stack.yaml names build {document.get('build')!r}"
    )
    assert isinstance(document.get("chapter"), int), (
        f"{build}/stack.yaml records no chapter"
    )

    rows = rows_of(document)
    missing = [field for field in FIELDS if field not in rows]
    assert not missing, (
        f"{build}/stack.yaml is missing {missing}. A row nobody answered is "
        f"written {UNSPECIFIED} rather than left out: an absent row reads as a "
        "system with nothing in that position, which is a different claim."
    )
    assert tuple(rows) == FIELDS, (
        f"{build}/stack.yaml answers {tuple(rows)}, not {FIELDS}"
    )

    for field in FIELDS:
        row = rows[field]
        assert row["question"] == TEMPLATE_ROWS[field]["question"], (
            f"{build}/stack.yaml asks a different {field} question than "
            "templates/stack.yaml. The twelve copies are held to one wording "
            "because a question that drifts is a different question."
        )
        value = row.get("value")
        assert isinstance(value, str) and value.strip(), (
            f"{build}/stack.yaml leaves {field} blank or null. Write "
            f"{UNSPECIFIED}: a blank says there is nothing in that position "
            "and an unanswered row says nobody decided, and Chapter 2 is "
            "about the difference."
        )
        assert isinstance(row.get("note"), str), (
            f"{build}/stack.yaml has no note field for {field}"
        )


@pytest.mark.parametrize("build", BUILDS)
def test_the_committed_inventory_is_what_the_build_emits(build: str):
    """Regenerate it and compare, so a stale inventory fails rather than lies.

    Run as a subprocess from inside the build folder, which is how a reader
    runs it and the only way twelve builds that share module names can each be
    asked what they contain.
    """
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, stack; sys.stdout.write(stack.as_yaml())"],
        cwd=BUILDS_ROOT / build, capture_output=True, text=True, check=False,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"{build}/stack.py does not run in its own folder:\n"
        f"{result.stderr[-2000:]}"
    )
    emitted = result.stdout.replace("\r\n", "\n")
    committed = inventory_path(build).read_text(encoding="utf-8")
    assert emitted == committed, (
        f"{build}/stack.yaml is not what {build}/stack.py emits today. The "
        "code moved and the inventory did not. Run `python stack.py` in that "
        "folder and commit the result."
    )


def test_the_count_of_unanswered_rows_is_the_recorded_one():
    """The number Chapter 2's argument is about, counted rather than asserted.

    Not a ceiling to keep under. It is a record of which rows nobody has
    settled, so that a new one arrives as a failing test rather than as a
    quiet third entry in a file nobody opens.
    """
    unanswered = {
        f"{build}.{field}"
        for build in BUILDS
        for field, row in rows_of(load(inventory_path(build))).items()
        if row.get("value") == UNSPECIFIED
    }
    assert len(unanswered) == UNSPECIFIED_ROWS, (
        f"{len(unanswered)} rows are {UNSPECIFIED} and this file records "
        f"{UNSPECIFIED_ROWS}: {sorted(unanswered)}. If a build stopped "
        "answering a question, that is the finding. If one was answered, "
        "lower the number here and delete its line from the comment above it."
    )
