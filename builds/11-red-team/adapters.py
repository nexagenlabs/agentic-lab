"""The earlier builds, behind a process boundary, and the checks added in front.

## Why subprocesses

There are two ways to reach the earlier builds: the isolation mechanism
settled in `docs/CONVENTIONS.md`,
or wrap each build behind a subprocess. This build uses subprocesses, for two
reasons.

The first is that the root `conftest.py` keeps exactly one build importable at
a time and re-activates it before every test. An adapter that swapped build 03
onto `sys.path` in the middle of a build 11 test would be fighting the
mechanism rather than using it, and the failure mode when it went wrong would
be the quiet one the mechanism exists to prevent: a `models` that belongs to
somebody else. A process boundary makes the invariant structural instead of
conventional, and it cannot be undone by accident.

The second is that this build's claim is about what the earlier builds do when
somebody runs them. A worker starts with exactly one build folder on the path
and no red-team module importable at all, which is the situation a reader is in
with one folder open. If the harness had to reach inside a build to make it
fail interestingly, that would be worth knowing, and this arrangement makes it
impossible to do by accident.

The cost is a process per target and a JSON line per fault. Workers are started
once and kept, so it is five processes for a whole run rather than one per
fault.

## Where a check came from

`Outcome` keeps `build_checks` and `harness_checks` apart, and merges them only
in `checks_fired`, which is what the printed `run_red_team` reads. That split is
the most useful thing in the file. A detection rate that mixes them says the
system caught 24 of 27; kept apart it says that the earlier builds caught 11 and
that 13 were caught by checks this build had to add, which is a different
sentence about the same run and the only one worth reporting.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Self

HERE = Path(__file__).resolve().parent
BUILDS = HERE.parent
WORKERS = HERE / "workers"

# A worker that has not answered in this long is not going to. The only jobs
# here are small and offline, so the timeout is a deadlock detector rather
# than a latency budget.
WORKER_TIMEOUT_S = 120.0


@dataclass
class Outcome:
    """What a pipeline did with one corrupted input.

    ``status`` matters as much as ``checks_fired``. The printed harness
    computes ``silent`` from it, and a fault that was missed while the run
    returned COMPLETE is the case the whole book is about.
    """

    status: str
    build_checks: list[str] = field(default_factory=list)
    harness_checks: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    answer: Any = None
    detail: str = ""

    @property
    def checks_fired(self) -> list[str]:
        return list(self.build_checks) + list(self.harness_checks)


class Pipeline(Protocol):
    def run(self, corrupted: Any) -> Outcome: ...


class WorkerError(RuntimeError):
    """The worker process died or answered something that is not a result."""


class WorkerPipeline:
    """One earlier build, in its own process, started once and kept.

    The worker is handed a build folder and nothing else. It puts that folder
    on its path, wires the build offline exactly as that build's own tests do,
    and answers one JSON line per job.
    """

    def __init__(self, worker: str, build: str, name: str | None = None) -> None:
        self.script = WORKERS / worker
        self.build = BUILDS / build
        self.name = name or build
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> Self:
        if self._process is None:
            self._process = subprocess.Popen(
                [sys.executable, "-u", str(self.script), str(self.build)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                cwd=str(self.build),
            )
        return self

    def run(self, corrupted: Any) -> Outcome:
        process = self.start()._process
        assert process is not None and process.stdin and process.stdout
        try:
            process.stdin.write(json.dumps(corrupted, default=str) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
        except (BrokenPipeError, OSError) as error:
            raise WorkerError(f"{self.name} worker died: {error}") from error
        if not line:
            stderr = process.stderr.read() if process.stderr else ""
            raise WorkerError(f"{self.name} worker produced nothing. {stderr}")
        body = json.loads(line)
        return Outcome(
            status=body["status"],
            build_checks=body.get("checks_fired", []),
            events=body.get("events", []),
            answer=body.get("answer"),
            detail=body.get("detail", ""),
        )

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.wait(timeout=WORKER_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
        finally:
            self._process = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.close()


class CheckedPipeline:
    """An earlier build with a check in front of it that it does not have.

    This is the arrangement a real deployment ends up in: the build does what
    it does, and the thing that catches fabricated citations sits at its output
    boundary because nobody is going to rewrite Build 03 to know about DOIs.

    Keeping the two apart in the ``Outcome`` is what lets the report say which
    of the two caught a fault, and that is the sentence worth reporting.
    """

    def __init__(self, inner: Pipeline,
                 checker: Callable[[Any, Outcome], list[str]],
                 name: str = "checked") -> None:
        self.inner = inner
        self.checker = checker
        self.name = name

    def run(self, corrupted: Any) -> Outcome:
        outcome = self.inner.run(corrupted)
        outcome.harness_checks = sorted(set(self.checker(corrupted, outcome)))
        return outcome

    def close(self) -> None:
        closer = getattr(self.inner, "close", None)
        if closer:
            closer()


class GuardedPipeline:
    """A check that runs BEFORE the pipeline, not after it.

    ``CheckedPipeline`` inspects an outcome, which is the right shape for a
    citation checker: the references are in the input either way and there is
    nothing to be gained by looking early.

    Drift is different, and the difference is the whole of Chapter 10's
    argument about it. A drift check that runs after the summary has been
    written is an incident report. It tells you the run went somewhere it
    should not have, once the output has already been produced and, in a real
    deployment, already been read. So the check runs first, its result is
    recorded first in ``events``, and the ordering is a property of this class
    rather than a claim in a docstring.

    The inner pipeline still runs, because the report needs to know what the
    build itself would have caught. What the gate asserts is the order.
    """

    def __init__(self, inner: Pipeline,
                 pre_checker: Callable[[Any], list[str]],
                 name: str = "guarded") -> None:
        self.inner = inner
        self.pre_checker = pre_checker
        self.name = name

    def run(self, corrupted: Any) -> Outcome:
        fired = sorted(set(self.pre_checker(corrupted)))
        events = ["drift_check_ran"]
        if fired:
            events.append("drift_check_fired")
        outcome = self.inner.run(corrupted)
        outcome.harness_checks = fired
        outcome.events = events + list(outcome.events)
        return outcome

    def close(self) -> None:
        closer = getattr(self.inner, "close", None)
        if closer:
            closer()


class CompositePipeline:
    """Several builds behind one ``run``, routed by ``job["target"]``.

    Both the fabrication family and the numeric family name two target builds
    in the spec, and the printed ``run_red_team`` takes one pipeline. Routing
    on a field of the corrupted input is the honest way to satisfy both: the
    fault says which build it is aimed at, because a fault aimed at the plate
    mapper is not a fault the wrangler could catch.
    """

    def __init__(self, targets: dict[str, Pipeline]) -> None:
        self.targets = targets

    def run(self, corrupted: Any) -> Outcome:
        target = corrupted.get("target")
        if target not in self.targets:
            raise WorkerError(
                f"job names target {target!r}, and this pipeline routes to "
                f"{sorted(self.targets)}"
            )
        return self.targets[target].run(corrupted)

    def close(self) -> None:
        for pipeline in self.targets.values():
            closer = getattr(pipeline, "close", None)
            if closer:
                closer()


class RecordingPipeline:
    """Wraps any pipeline and keeps every outcome, for the report."""

    def __init__(self, inner: Pipeline) -> None:
        self.inner = inner
        self.outcomes: list[Outcome] = []

    def run(self, corrupted: Any) -> Outcome:
        outcome = self.inner.run(corrupted)
        self.outcomes.append(outcome)
        return outcome

    def close(self) -> None:
        closer = getattr(self.inner, "close", None)
        if closer:
            closer()
