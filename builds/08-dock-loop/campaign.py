"""One campaign, and the manifest that is enough to run it again.

The manifest is not a log written afterwards. It is the input: everything the
run needed is in it, so re-running means handing it back rather than
reconstructing what somebody probably did. That is the property Chapter 9
depends on, and the way to get it is to make the manifest the thing the runner
reads in the first place.

Two fields in it are easy to leave out and fatal to leave out. The seed,
because the search is stochastic. The exhaustiveness, because it decides how
hard the search tried and a run at 8 is not a repeat of a run at 32.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from comparison import ComparisonSet
from engine import DockingEngine
from models import (
    DockingBox,
    DockingResult,
    PreparationDecisions,
    StructureRecord,
)
from parse import parse_poses
from pydantic import BaseModel, ConfigDict, Field
from rank import RankedEntry, rank_results

# What two runs of the same manifest are allowed to differ by. With a recorded
# engine the answer is exactly nothing, and the tolerance exists for the live
# case: Vina at a fixed seed and exhaustiveness reproduces its scores to about
# a hundredth of a kcal/mol, and a difference larger than that means something
# other than the search changed.
SCORE_TOLERANCE = 0.01


class RunManifest(BaseModel):
    """Everything the run needed, in the order somebody would need it back."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    engine: str
    seed: int
    exhaustiveness: int = Field(ge=1)
    comparison_set_id: str
    boxes: dict[str, DockingBox]
    preparation: PreparationDecisions
    structures: dict[str, StructureRecord]
    pairs: list[tuple[str, str]] = Field(min_length=1)
    # Written down because it was passed. A mixed set is defensible; a mixed
    # set nobody recorded as mixed is not.
    allow_mixed_provenance: bool = False
    score_tolerance: float = SCORE_TOLERANCE


@dataclass
class Campaign:
    """What a run produced, beside the manifest that produced it."""

    manifest: RunManifest
    results: list[DockingResult]
    ranking: list[RankedEntry]

    def scores(self) -> dict[tuple[str, str], float]:
        return {(r.target, r.ligand_id): r.top_score for r in self.results}


def _dock_pairs(
    pairs: list[tuple[str, str]],
    boxes: dict[str, DockingBox],
    engine: DockingEngine,
    seed: int,
    exhaustiveness: int,
    trace: Any = None,
) -> list[DockingResult]:
    results = []
    for target, ligand_id in pairs:
        output = engine.dock(target, ligand_id, boxes[target],
                             seed=seed, exhaustiveness=exhaustiveness)
        poses = parse_poses(output)
        result = DockingResult(
            ligand_id=ligand_id, target=target, poses=poses,
            seed=seed, exhaustiveness=exhaustiveness, engine=engine.name,
        )
        if trace is not None:
            trace.write("docked", target=target, ligand_id=ligand_id,
                        poses=len(poses), top_score=result.top_score,
                        seed=seed, exhaustiveness=exhaustiveness)
        results.append(result)
    return results


def run_campaign(
    pairs: list[tuple[str, str]],
    comparison_set: ComparisonSet,
    records: dict[str, StructureRecord],
    preparation: PreparationDecisions,
    engine: DockingEngine,
    *,
    seed: int,
    exhaustiveness: int,
    allow_mixed_provenance: bool = False,
    trace: Any = None,
) -> Campaign:
    """Dock every pair, rank the result, and record what it took."""
    manifest = RunManifest(
        run_id=uuid.uuid4().hex[:12],
        engine=engine.name,
        seed=seed,
        exhaustiveness=exhaustiveness,
        comparison_set_id=comparison_set.comparison_set_id,
        boxes=comparison_set.boxes,
        preparation=preparation,
        structures={target: records[target] for target, _ in pairs},
        pairs=list(pairs),
        allow_mixed_provenance=allow_mixed_provenance,
    )
    if trace is not None:
        trace.write("campaign_started", run_id=manifest.run_id,
                    engine=manifest.engine, seed=seed,
                    exhaustiveness=exhaustiveness,
                    comparison_set_id=manifest.comparison_set_id,
                    allow_mixed_provenance=allow_mixed_provenance)

    results = _dock_pairs(pairs, comparison_set.boxes, engine, seed,
                          exhaustiveness, trace)
    ranking = rank_results(results, records,
                           allow_mixed_provenance=allow_mixed_provenance)

    if trace is not None:
        trace.write("campaign_complete", run_id=manifest.run_id,
                    ranked=len(ranking))
    return Campaign(manifest=manifest, results=results, ranking=ranking)


def rerun_from_manifest(
    manifest: RunManifest, engine: DockingEngine, *, trace: Any = None,
) -> list[DockingResult]:
    """Run it again from the manifest and nothing else."""
    return _dock_pairs(
        [(target, ligand) for target, ligand in manifest.pairs],
        manifest.boxes, engine, manifest.seed, manifest.exhaustiveness, trace,
    )


def scores_agree(
    first: list[DockingResult], second: list[DockingResult],
    tolerance: float = SCORE_TOLERANCE,
) -> list[str]:
    """Which pairs disagree by more than the documented tolerance."""
    left = {(r.target, r.ligand_id): r.top_score for r in first}
    right = {(r.target, r.ligand_id): r.top_score for r in second}
    if left.keys() != right.keys():
        return [f"different pairs: {sorted(left.keys() ^ right.keys())}"]
    return [
        f"{target}/{ligand}: {left[(target, ligand)]} against "
        f"{right[(target, ligand)]}"
        for target, ligand in left
        if abs(left[(target, ligand)] - right[(target, ligand)]) > tolerance
    ]
