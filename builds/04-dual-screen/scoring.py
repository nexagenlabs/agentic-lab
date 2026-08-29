"""Where the two screens finally meet, and the only place they do.

Both screens are finished and written to disk before this module reads either
of them. Nothing here can influence a verdict: by the time ``score_run`` is
called, every verdict already exists in a file that the other screen never saw.

The sensitivity threshold is a required argument. A default would let a caller
compute a result and then decide what would have counted as passing, which is
the same mistake as choosing an endpoint after seeing the data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adjudicate import find_disagreements, write_adjudication
from goldset import GoldSet
from metrics import agreement, score_against_gold
from report import write_report
from screens import ScreenPlan, load_screen


class ScoringError(RuntimeError):
    """The two screens cannot be compared as they stand."""


def _decisions(screen: dict[str, Any]) -> dict[str, str]:
    return {v.pmid: v.decision for v in screen["verdicts"]}


def check_criteria_versions(
    screen_a: dict[str, Any], screen_b: dict[str, Any], criteria_version: int
) -> int:
    """Refuse to score screens run under different criteria.

    Two screens judged against different rules are not two screens, and an
    agreement statistic over them measures the difference between the rules
    rather than the difference between the screens.
    """
    versions = {screen_a["criteria_version"], screen_b["criteria_version"]}
    if len(versions) > 1:
        raise ScoringError(
            f"the two screens were run under different criteria versions "
            f"{sorted(versions)}. Comparing them would measure the change in "
            "the criteria, not the disagreement between the screens."
        )

    only = versions.pop()
    if only != criteria_version:
        raise ScoringError(
            f"the screens were run under criteria version {only}, but the "
            f"criteria file on disk is version {criteria_version}. Rerun the "
            "screens or check out the criteria they were run against."
        )

    for screen in (screen_a, screen_b):
        stale = sorted(
            v.pmid for v in screen["verdicts"] if v.criteria_version != only
        )
        if stale:
            raise ScoringError(
                f"screen {screen['screen']!r} has verdicts stamped with a "
                f"different criteria version: {stale[:5]}"
            )
    return only


def score_run(
    screen_a_path: str | Path,
    screen_b_path: str | Path,
    gold_set: GoldSet,
    *,
    sensitivity_threshold: float,
    plan: ScreenPlan,
    criteria_version: int,
    criteria_file: str | Path,
    run_id: str,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Score two finished screens and emit the manifest, report and adjudication."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    screen_a = load_screen(screen_a_path)
    screen_b = load_screen(screen_b_path)
    version = check_criteria_versions(screen_a, screen_b, criteria_version)

    decisions_a = _decisions(screen_a)
    decisions_b = _decisions(screen_b)

    performance = score_against_gold(decisions_a, gold_set.labels)
    performance_b = score_against_gold(decisions_b, gold_set.labels)
    observed = agreement(decisions_a, decisions_b)

    adjudication = find_disagreements(screen_a["verdicts"], screen_b["verdicts"])
    adjudication_file = write_adjudication(out_dir / "adjudication.json", adjudication)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "corpus_size": len(decisions_a),
        "criteria_version": version,
        # Posix separators: this path is quoted into a document someone pastes
        # into a methods section, and a Windows path there reads as a mistake.
        "criteria_file": Path(criteria_file).as_posix(),
        "screens": plan.describe(),
        "gold_set": gold_set.composition(),
        "sensitivity_threshold": sensitivity_threshold,
        "sensitivity_met": performance.sensitivity >= sensitivity_threshold,
        "screen_a_performance": performance.as_dict(),
        "screen_b_performance": performance_b.as_dict(),
        "agreement": observed.as_dict(),
        "adjudication": adjudication.as_dict() | {"disagreements": None},
        "adjudication_file": Path(adjudication_file).as_posix(),
    }
    # The disagreement bodies live in their own file. Repeating them in the
    # manifest would invite someone to read the copy and edit the original.
    manifest["adjudication"].pop("disagreements")

    report_file = write_report(out_dir / "screen_report.md", manifest)
    manifest["report_file"] = Path(report_file).as_posix()

    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
