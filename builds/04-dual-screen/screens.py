"""Two screens that cannot see each other, and the three configurations.

Independence here is structural rather than asserted. It rests on three
things, and none of them is a promise in a docstring.

``run_screen`` takes the records, a prompt builder, a model and an output
path. There is no parameter through which another screen's verdicts could
reach it, so no amount of careless calling can leak one screen into the other.

Each screen writes its own file. They meet for the first time in
``load_screen``, at scoring time, after both are finished and neither can be
influenced by the other.

The two prompts differ, and the two models differ, and ``plan_screens``
refuses a configuration where they do not. Two identical screens agreeing
measures the temperature setting.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from criteria import Criteria
from models import Verdict
from prompts import build_task_a, build_task_b

MODES = ("two_agents", "agent_and_human", "same_agent_twice")

SAME_AGENT_REFUSAL = (
    "same_agent_twice is not a second reviewer. Running one model over the "
    "same records twice measures inter-run stability: a high agreement tells "
    "you the temperature is low and tells you nothing about whether the "
    "decisions are right. Two screens that share a model share its blind "
    "spots, and no agreement statistic can see a blind spot both screens "
    "have. Pass acknowledge_not_a_second_reviewer=True to say you understand "
    "that this run measures stability and not correctness."
)


class ScreenConfigurationError(RuntimeError):
    """The requested pair of screens would not be two independent screens."""


@dataclass(frozen=True)
class ScreenPlan:
    """What the two chairs are, decided before either screen runs."""

    mode: str
    model_a: str
    model_b: str
    prompt_a: Callable[[dict[str, Any], Criteria], str]
    prompt_b: Callable[[dict[str, Any], Criteria], str] | None
    human_file: Path | None = None

    def describe(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "screen_a": self.model_a,
            "screen_b": self.model_b,
            "human_file": str(self.human_file) if self.human_file else "",
        }


def plan_screens(
    mode: str = "two_agents",
    *,
    model_a: str,
    model_b: str | None = None,
    human_file: str | Path | None = None,
    acknowledge_not_a_second_reviewer: bool = False,
) -> ScreenPlan:
    """Choose a configuration, or refuse to.

    The refusals are the point of this function. A configuration that cannot
    produce two independent verdicts is rejected here, before any record is
    screened, rather than producing a number that looks like agreement.
    """
    if mode not in MODES:
        raise ScreenConfigurationError(
            f"unknown mode {mode!r}, expected one of {', '.join(MODES)}"
        )

    if mode == "same_agent_twice":
        if not acknowledge_not_a_second_reviewer:
            raise ScreenConfigurationError(SAME_AGENT_REFUSAL)
        return ScreenPlan("same_agent_twice", model_a, model_a,
                          build_task_a, build_task_a)

    if mode == "agent_and_human":
        if human_file is None:
            raise ScreenConfigurationError(
                "agent_and_human needs human_file: the second chair reads "
                "verdicts a person wrote, and there is nothing to read without it"
            )
        return ScreenPlan("agent_and_human", model_a, "human",
                          build_task_a, None, Path(human_file))

    if model_b is None:
        raise ScreenConfigurationError("two_agents needs model_b")
    if model_a == model_b:
        raise ScreenConfigurationError(
            f"two_agents was given the same model twice ({model_a!r}). That is "
            "same_agent_twice wearing a different name, and it measures "
            "stability rather than agreement. Use mode='same_agent_twice' and "
            "acknowledge it, or supply two different models."
        )
    return ScreenPlan("two_agents", model_a, model_b, build_task_a, build_task_b)


def run_screen(
    pmids: Iterable[str],
    criteria: Criteria,
    *,
    model: str,
    prompt_builder: Callable[[dict[str, Any], Criteria], str],
    fetch: Callable[[str], dict[str, Any]],
    run_agent: Callable[..., dict[str, Any]],
    out_path: str | Path,
    trace: Any,
    screen_name: str,
    max_steps: int = 4,
) -> list[Verdict]:
    """Screen every record and write the verdicts to their own file.

    Note what is absent from this signature. There is no parameter carrying
    another screen's verdicts, no shared mutable store, and no return path by
    which one screen could reach another. The only way the two screens meet is
    ``load_screen`` reading two finished files.

    Every record leaves a verdict or a logged gap, as in Build 03.
    """
    verdicts: list[Verdict] = []
    failed: list[str] = []
    pmids = list(pmids)

    trace.write("screen_start", screen=screen_name, model=model,
                records=len(pmids), criteria_version=criteria.version)

    for pmid in pmids:
        record = fetch(pmid)
        result = run_agent(prompt_builder(record, criteria), max_steps=4,
                           model=model)
        if result["status"] != "COMPLETE":
            trace.write("record_failed", screen=screen_name, pmid=pmid,
                        reason=result["status"])
            failed.append(pmid)
            continue
        verdicts.append(Verdict(**result["answer"]))

    # Arithmetic in Python. Every record is a verdict or a logged gap.
    assert len(verdicts) + len(failed) == len(pmids)

    write_screen(out_path, verdicts, model=model, screen_name=screen_name,
                 criteria_version=criteria.version, failed=failed)
    trace.write("screen_complete", screen=screen_name, model=model,
                verdicts=len(verdicts), failed=len(failed), path=str(out_path))
    return verdicts


def write_screen(
    path: str | Path,
    verdicts: list[Verdict],
    *,
    model: str,
    screen_name: str,
    criteria_version: int,
    failed: list[str] | None = None,
) -> Path:
    """Write one screen's output, and only that screen's output."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "screen": screen_name,
        "model": model,
        "criteria_version": criteria_version,
        "failed": sorted(failed or []),
        "verdicts": [v.model_dump() for v in verdicts],
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def load_screen(path: str | Path) -> dict[str, Any]:
    """Read one finished screen. This is where the two first meet."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("screen", "model", "criteria_version", "verdicts"):
        if key not in data:
            raise ScreenConfigurationError(f"screen file is missing {key!r}: {path}")
    data["verdicts"] = [Verdict(**v) for v in data["verdicts"]]
    return data


def load_human_screen(path: str | Path, *, criteria_version: int) -> dict[str, Any]:
    """Read verdicts a person wrote, and hold them to the same shape.

    A human screen is not exempt from validation. A hand-written file with a
    missing field or a stale criteria version would otherwise be scored as
    though it were sound, and the resulting statistics would describe a
    comparison that never happened.
    """
    data = load_screen(path)
    if data["criteria_version"] != criteria_version:
        raise ScreenConfigurationError(
            f"human verdicts were recorded under criteria version "
            f"{data['criteria_version']}, but this run uses {criteria_version}"
        )
    return data
