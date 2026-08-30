"""Assertion mutation: does neutering a guard make a test fail?

Five times now this repository has held a check that could be deleted without
a single test noticing. Three were guards documented as enforcement and never
enforced, and two were tests that could not fail. Each was found by hand, by
somebody who thought to try, and hand discovery does not repeat on a schedule.

So this is the schedule. Every guard the book names is neutered in a throwaway
copy of the repository, one at a time, and the test that is supposed to notice
is run against the damage. A guard whose removal changes nothing is reported
by name.

Two rules keep this from becoming the decoration it exists to prevent:

  * A guard in ``CAUGHT`` must make its named test fail. Not "some test in the
    repository", the named one, because a guard covered only by accident is
    covered until somebody edits the test that was catching it by accident.
  * A guard in ``SURVIVORS`` must still survive. When one starts being caught,
    this gate fails and tells you to delete the entry. The list can therefore
    only ever shrink, and a hole cannot be quietly re-admitted to it.

The survivors are real holes, recorded rather than hidden, each with the
PLAN.md item that will close it. Recording them is not blessing them.

Running time is about fifteen seconds because the mutants run concurrently
against one repository copy per worker, and each names the single test that
should fail rather than running a whole gate. The exception is a survivor,
where the claim is that nothing in that build notices, so the whole build gate
has to run before the claim can be made.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKERS = 4

# The end-to-end test runs the other eleven gates in a subprocess, and this
# module runs them again, once per mutant. Nesting the two multiplies out to
# minutes of the same tests, so Build 12's own gate is entered here by the one
# test that exercises its checkpoints.
END_TO_END = (
    "builds/12-repurposing-desk/tests/test_desk.py::"
    "test_all_prior_gates_pass_in_sequence"
)
DESELECT_END_TO_END = ("--deselect", END_TO_END)


@dataclass(frozen=True)
class Guard:
    """One check, and the mutation that removes it.

    ``old`` is matched inside ``function`` only, so an anchor as ordinary as
    ``if offenders:`` is unambiguous, and a rename of the function it lives in
    fails this gate loudly rather than silently mutating nothing.
    """

    name: str
    build: str
    module: str
    function: str
    old: str
    new: str
    target: tuple[str, ...]
    why: str

    @property
    def path(self) -> Path:
        return Path("builds") / self.build / self.module


# Neutering the condition leaves the raise unreachable, which is what a guard
# looks like after somebody "simplifies" it.
OFF = "if False:"

# Test node ids, named here so the registry below stays one line per field.
# ruff reads an implicit concatenation inside a tuple as a missing comma, which
# it usually is, so the joins happen out here instead.
T_STEP_CAP = (
    "builds/01-first-agent/tests/test_agent.py::test_step_cap_marks_incomplete"
)
T_BUDGET = (
    "builds/01-first-agent/tests/test_agent.py::test_budget_halts_before_the_call"
)
T_ROW_CONSERVATION = (
    "builds/05-wrangler/tests/test_wrangler.py::test_row_conservation"
)
T_CORRUPTIONS = (
    "builds/05-wrangler/tests/test_wrangler.py::test_schema_rejects_known_corruptions"
)
T_NO_WRITE = (
    "builds/09-eln-bridge/tests/test_eln_bridge.py::test_no_write_without_approval"
)
T_INPUT_DRIFT = (
    "builds/10-run-manifest/tests/test_run_manifest.py::test_manifest_detects_input_drift"
)
T_HALT_REASON = (
    "builds/10-run-manifest/tests/test_run_manifest.py::"
    "test_a_complete_run_may_not_carry_a_halt_reason"
)
T_CHECKPOINTS = (
    "builds/12-repurposing-desk/tests/test_desk.py::"
    "test_no_stage_proceeds_past_an_unapproved_checkpoint"
)

CAUGHT: tuple[Guard, ...] = (
    Guard(
        "step_cap_returns_incomplete", "01-first-agent", "agent.py", "run_agent",
        '"status": "INCOMPLETE", "reason": "step_cap"',
        '"status": "COMPLETE", "reason": "step_cap"',
        (T_STEP_CAP,),
        "the book's central failure mode: a run that hit its cap calling itself"
        " finished",
    ),
    Guard(
        "budget_checked_before_the_call", "01-first-agent", "agent.py", "run_agent",
        "if tokens_used + estimated_next > token_budget:", OFF,
        (T_BUDGET,),
        "a budget checked after the call is one that has already been spent",
    ),
    Guard(
        "row_conservation", "05-wrangler", "assertions.py",
        "assert_row_conservation",
        "if actual != expected.expected_rows:", OFF,
        (T_ROW_CONSERVATION,),
        "assertion 1 of Table 5.2",
    ),
    Guard(
        "silent_nulls", "05-wrangler", "assertions.py", "assert_no_silent_nulls",
        "if delta != expected.declared_new_nulls:", OFF,
        (T_CORRUPTIONS,),
        "assertion 2 of Table 5.2",
    ),
    Guard(
        "units_declared", "05-wrangler", "assertions.py", "assert_units_declared",
        "if offenders:", OFF,
        (T_CORRUPTIONS,),
        "assertion 3 of Table 5.2, and the rule that units live in column names",
    ),
    Guard(
        "range_plausibility", "05-wrangler", "assertions.py",
        "assert_ranges_plausible",
        "if offenders:", OFF,
        (T_CORRUPTIONS,),
        "assertion 4 of Table 5.2",
    ),
    Guard(
        "identifier_integrity", "05-wrangler", "assertions.py",
        "assert_identifier_integrity",
        "if unknown or absent:", OFF,
        (T_CORRUPTIONS,),
        "assertion 5 of Table 5.2",
    ),
    Guard(
        "not_approved", "09-eln-bridge", "notebook.py", "authorise",
        "if not proposal.is_approved:", OFF,
        (T_NO_WRITE,),
        "Chapter 8: an approval without an identity is not an approval",
    ),
    Guard(
        "input_hash_verified", "10-run-manifest", "replay.py", "verify_inputs",
        "if actual != record.sha256:", OFF,
        (T_INPUT_DRIFT,),
        "a manifest whose input hashes are not checked is decorative",
    ),
    Guard(
        "halt_reason_agrees_with_status", "10-run-manifest", "models.py",
        "_halt_reason_agrees_with_status",
        'if self.status == "COMPLETE" and self.halt_reason is not None:', OFF,
        (T_HALT_REASON,),
        "a run cannot have both finished and halted",
    ),
    Guard(
        "approval_is_for_different_content", "12-repurposing-desk",
        "checkpoints.py", "checkpoint",
        "if approval.reviewed_sha256 != digest:", OFF,
        (T_CHECKPOINTS,),
        "an approval signed over other content is not a record of anybody"
        " having looked at this",
    ),
)

# Holes. Each is a guard the surrounding chapter argues for, which no test in
# its build notices the loss of. They are listed so that the gate is honest
# about what it found rather than green because nobody asked.
SURVIVORS: tuple[Guard, ...] = (
    Guard(
        "determinism_assertion", "05-wrangler", "assertions.py",
        "assert_deterministic",
        "if first != second:", OFF,
        ("builds/05-wrangler/tests",),
        "PLAN.md B4. The sixth assertion of Table 5.2. The determinism"
        " property is covered by test_transform_is_deterministic, which"
        " compares the bytes itself; the assertion inside the shipped"
        " pipeline, which is the part a reader copies, is not.",
    ),
    Guard(
        "machine_attribution", "09-eln-bridge", "notebook.py", "authorise",
        'if not str(getattr(proposal, field) or "").strip():', OFF,
        ("builds/09-eln-bridge/tests",),
        "PLAN.md B3. Chapter 8 says every entry this build writes carries"
        " machine attribution. Its sibling guard, not_approved, is covered"
        " properly, which is how the gap in this one stayed invisible.",
    ),
    Guard(
        "approval_without_identity", "12-repurposing-desk", "checkpoints.py",
        "checkpoint",
        "if not approval.is_approval:", OFF,
        ("builds/12-repurposing-desk/tests", *DESELECT_END_TO_END),
        "Found by this gate while it was being written. The comment above the"
        " tampering block in test_no_stage_proceeds_past_an_unapproved_"
        "checkpoint says an approval with no named identity is refused too,"
        " and only the content half is exercised. The prose is the coverage.",
    ),
)

ALL: tuple[Guard, ...] = CAUGHT + SURVIVORS


def span_of(source: str, function: str) -> tuple[int, int]:
    """The line range of one function, so an anchor is matched inside it."""
    found = [
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function
    ]
    if len(found) != 1:
        raise AssertionError(
            f"expected exactly one function named {function!r}, found "
            f"{len(found)}. The registry in this file names a function that "
            "has been renamed or duplicated, so its guard is no longer being "
            "mutated."
        )
    return found[0].lineno - 1, found[0].end_lineno


def apply_mutation(root: Path, guard: Guard) -> str:
    """Neuter one guard in the copy, returning the original source."""
    path = root / guard.path
    source = path.read_text(encoding="utf-8")
    start, end = span_of(source, guard.function)
    lines = source.splitlines(keepends=True)
    body = "".join(lines[start:end])
    if body.count(guard.old) != 1:
        raise AssertionError(
            f"{guard.name}: the anchor {guard.old!r} appears "
            f"{body.count(guard.old)} times in {guard.function}, and must "
            "appear once. The guard has moved, and this gate has been "
            "mutating nothing."
        )
    lines[start:end] = [body.replace(guard.old, guard.new, 1)]
    path.write_text("".join(lines), encoding="utf-8")
    return source


def run_target(root: Path, guard: Guard) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *guard.target, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=root, capture_output=True, text=True, check=False, timeout=900,
        env=environment,
    )


def probe(root: Path, guard: Guard) -> tuple[bool, str]:
    """Neuter the guard, run its target, put the file back.

    The restore is in a finally because a worker that died holding a mutated
    copy would hand the next guard a repository with two guards missing, and
    the result would look like coverage that is not there.
    """
    path = root / guard.path
    original = apply_mutation(root, guard)
    try:
        result = run_target(root, guard)
    finally:
        path.write_text(original, encoding="utf-8")
    tail = result.stdout.strip().splitlines()[-1:] or ["no pytest summary"]
    return result.returncode != 0, tail[0]


@pytest.fixture(scope="session")
def mutation_results(tmp_path_factory) -> dict[str, tuple[bool, str]]:
    """Every guard probed once, concurrently, one repository copy per worker."""
    base = tmp_path_factory.mktemp("mutation")
    copies: Queue[Path] = Queue()
    for index in range(WORKERS):
        root = base / f"repo{index}"
        shutil.copytree(REPO, root, ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
            "*.pyc", "htmlcov", "site",
        ))
        copies.put(root)

    def work(guard: Guard) -> tuple[str, tuple[bool, str]]:
        root = copies.get()
        try:
            return guard.name, probe(root, guard)
        finally:
            copies.put(root)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return dict(pool.map(work, ALL))


@pytest.mark.parametrize("guard", CAUGHT, ids=[g.name for g in CAUGHT])
def test_neutering_a_guard_fails_its_named_test(guard: Guard, mutation_results):
    caught, summary = mutation_results[guard.name]
    assert caught, (
        f"\n{guard.name} survived mutation.\n"
        f"  file:     {guard.path.as_posix()}, in {guard.function}\n"
        f"  mutation: {guard.old}  ->  {guard.new}\n"
        f"  target:   {' '.join(guard.target)}\n"
        f"  result:   {summary}\n"
        f"  why it matters: {guard.why}\n\n"
        "The guard can be deleted and the test that is supposed to notice "
        "passes anyway. Either the test never exercised it, or a change "
        "moved the coverage somewhere else. A green test that was never in "
        "danger of going red is decoration."
    )


@pytest.mark.parametrize("guard", SURVIVORS, ids=[g.name for g in SURVIVORS])
def test_a_recorded_survivor_still_survives(guard: Guard, mutation_results):
    """Good news arrives here as a failure.

    A survivor that starts being caught means somebody closed the hole, and
    the entry has to go so the list keeps meaning what it says. Without this
    the list would be an allowlist, and an allowlist nobody prunes is how a
    known hole becomes a permanent one.
    """
    caught, summary = mutation_results[guard.name]
    assert not caught, (
        f"\n{guard.name} is now caught, and is recorded as surviving.\n"
        f"  result: {summary}\n\n"
        "Delete its entry from SURVIVORS in this file, and the corresponding "
        "item from PLAN.md. This assertion is the only thing stopping the "
        "recorded list of holes from outliving the holes."
    )


def test_every_guard_in_the_registry_is_reachable():
    """The registry is checked against the repository, not only the copies.

    A guard whose file or function has been renamed would otherwise fail only
    inside a worker, where the message is buried under a subprocess summary.
    """
    for guard in ALL:
        path = REPO / guard.path
        assert path.exists(), f"{guard.name}: {guard.path.as_posix()} is gone"
        source = path.read_text(encoding="utf-8")
        start, end = span_of(source, guard.function)
        body = "".join(source.splitlines(keepends=True)[start:end])
        assert body.count(guard.old) == 1, (
            f"{guard.name}: anchor {guard.old!r} appears "
            f"{body.count(guard.old)} times in {guard.function}"
        )
