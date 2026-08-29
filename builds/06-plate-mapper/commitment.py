"""Did the model get chosen before the data existed?

Some readers will find comparing a file timestamp to a data timestamp
excessive, so here is the reason in full.

A synergy model chosen after the surfaces are drawn leaves no trace anywhere
that a reader can find. It is not visible in the analysis, because the
analysis runs the chosen model and reports it. It is not visible in the
figures, because the figures show the model that was run. It is not visible in
the manuscript, because the methods section describes what was done and not
when it was decided. Every artefact of the study is consistent with the model
having been chosen first.

The timestamp is the only surviving evidence. That is why it is checked rather
than trusted, and why the check is a hard failure rather than a warning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from design import Design, DesignError, load_design


@dataclass(frozen=True)
class Reading:
    """One dated measurement from the results directory."""

    path: Path
    recorded_at: datetime


class CommitmentError(RuntimeError):
    """The commitment does not precede the data."""

    def __init__(self, failure: str, detail: str) -> None:
        super().__init__(f"{failure}: {detail}")
        self.failure = failure
        self.detail = detail


def _as_utc(moment: datetime) -> datetime:
    """Compare instants, not wall clocks.

    The printed design carries an India Standard Time offset. A naive
    comparison against a UTC reading would be wrong by five and a half hours,
    which is easily enough to flip the answer.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def read_results(results_dir: str | Path) -> list[Reading]:
    """Every dated reading in the directory, earliest first."""
    results_dir = Path(results_dir)
    readings: list[Reading] = []
    for path in sorted(results_dir.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        stamp = body.get("recorded_at")
        if stamp is None:
            raise CommitmentError(
                "undated_reading",
                f"{path.name} carries no recorded_at, so nothing can be said "
                "about whether it predates the commitment",
            )
        readings.append(Reading(path, _as_utc(datetime.fromisoformat(stamp))))
    return sorted(readings, key=lambda r: r.recorded_at)


def check_commitment_precedes_data(
    design_path: str | Path, results_dir: str | Path
) -> dict[str, Any]:
    """Fail if the synergy model was chosen after data existed."""
    design: Design = load_design(design_path)
    if design.analysis is None:
        raise DesignError(
            "no_synergy_model",
            "there is no commitment to check; the design names no model",
        )

    committed = _as_utc(design.analysis.committed_at)
    readings = read_results(results_dir)

    if not readings:
        return {
            "committed_at": committed.isoformat(),
            "earliest_reading": None,
            "readings": 0,
            "verdict": "no data yet, so the commitment cannot be post hoc",
        }

    earliest = readings[0]
    if committed >= earliest.recorded_at:
        raise CommitmentError(
            "commitment_after_data",
            f"the synergy model {design.analysis.synergy_model!r} was "
            f"committed at {committed.isoformat()}, which is not before the "
            f"earliest reading at {earliest.recorded_at.isoformat()} "
            f"({earliest.path.name}). A model chosen once data exists leaves "
            "no trace in the analysis, the figures or the manuscript, so this "
            "timestamp is the only evidence either way.",
        )

    margin = earliest.recorded_at - committed
    return {
        "committed_at": committed.isoformat(),
        "earliest_reading": earliest.recorded_at.isoformat(),
        "earliest_file": earliest.path.name,
        "readings": len(readings),
        "margin_hours": round(margin.total_seconds() / 3600, 2),
        "verdict": "the model was committed before any data existed",
    }
