"""The red-team result, written into a run manifest. All of it.

Build 10's manifest shape, copied rather than imported, carrying one extra
section. The extra section is the point of the file: a harness that recorded
only its successes would be this chapter's failure one level up, so the
manifest carries the misses, the silent misses and the per-family denominators,
and there is no code path that writes a summary without them.

``detection_rate`` is deliberately absent as a scalar. The manifest records
``caught`` and ``planted`` as two integers and the sentence in ``summary``
carries both. A single float in a manifest is the thing that gets copied into a
slide, and by the time it is on the slide nobody can ask what the denominator
was.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness import Report
from pydantic import BaseModel, ConfigDict, Field


class RedTeamRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    python_version: str = Field(default_factory=platform.python_version)
    families: list[str] = Field(default_factory=list)
    # The pipelines the faults were run against, named, because "the system
    # caught 25 of 25" means nothing without knowing what the system was.
    pipeline: str = "unspecified"
    caught: int = 0
    planted: int = 0
    summary: str = ""
    missed: list[str] = Field(default_factory=list)
    silent_misses: list[str] = Field(default_factory=list)
    by_family: dict[str, dict[str, int]] = Field(default_factory=dict)
    controls_that_fired: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)

    def describe(self) -> str:
        return (
            f"Red team {self.run_id} against {self.pipeline}: {self.summary}. "
            f"Every fault planted is listed, caught or not."
        )


def record(run_id: str, pipeline: str, report: Report,
           controls_that_fired: list[str] | None = None,
           started_at: datetime | None = None) -> RedTeamRun:
    """Turn a report into a manifest section, losing nothing on the way."""
    body = report.as_dict()
    return RedTeamRun(
        run_id=run_id,
        started_at=started_at or datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        families=report.families,
        pipeline=pipeline,
        caught=body["caught"],
        planted=body["planted"],
        summary=body["summary"],
        missed=body["missed"],
        silent_misses=body["silent_misses"],
        by_family=body["by_family"],
        controls_that_fired=list(controls_that_fired or []),
        results=body["results"],
    )


def write(run: RedTeamRun, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return path
