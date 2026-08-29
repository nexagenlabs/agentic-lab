"""The two controls that run inside the campaign rather than beside it.

This is the build where the agent can be working perfectly and the science
still be worthless, so the gate is sceptical in a way the other builds are
not. Two of its checks are not checks on the code. They are experiments the
campaign runs on itself, and they are the reason to believe anything it says
about a compound nobody has tested.

Redocking: take a receptor whose ligand pose is known, strip the ligand, dock
it back. If the setup cannot recover an answer it already has, nothing it says
about an unknown compound is worth reading.

Enrichment: dock known actives alongside property-matched decoys. Enrichment
is the claim docking supports, so it is the claim that gets measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from geometry import cluster_occupancy, rmsd
from models import DockingResult
from rank import enrichment_factor


class ControlFailed(RuntimeError):
    """A control that did not clear its threshold, with the numbers."""

    def __init__(self, code: str, detail: str, **numbers: float) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.numbers = numbers

    def as_dict(self) -> dict[str, object]:
        return {"status": "FAILED", "code": self.code, "detail": self.detail,
                **self.numbers}


@dataclass(frozen=True)
class RedockingControl:
    """What the redock recovered, whether or not it cleared the threshold."""

    ligand_id: str
    target: str
    top_pose_rmsd: float
    best_pose_rmsd: float
    best_pose_rank: int
    cluster_occupancy: int
    threshold_angstrom: float

    @property
    def passed(self) -> bool:
        return self.top_pose_rmsd <= self.threshold_angstrom


def redocking_control(
    result: DockingResult,
    crystal_pose: list[tuple[float, float, float]],
    *,
    threshold_angstrom: float,
) -> RedockingControl:
    """Compare the docked poses against the pose that was already known.

    The threshold is passed in. Two angstroms is the convention and it is a
    convention, not a law, so it is stated at the call site where a reader can
    argue with it rather than buried here.
    """
    by_rmsd = sorted(
        ((rmsd(pose.coordinates, crystal_pose), pose) for pose in result.poses),
        key=lambda item: (item[0], item[1].rank),
    )
    best_rmsd, best_pose = by_rmsd[0]
    return RedockingControl(
        ligand_id=result.ligand_id,
        target=result.target,
        top_pose_rmsd=rmsd(result.top.coordinates, crystal_pose),
        best_pose_rmsd=best_rmsd,
        best_pose_rank=best_pose.rank,
        cluster_occupancy=cluster_occupancy(result.poses),
        threshold_angstrom=threshold_angstrom,
    )


@dataclass(frozen=True)
class EnrichmentControl:
    """Enrichment at one stated fraction, with the counts behind it."""

    fraction: float
    factor: float
    threshold: float
    actives: int
    decoys: int
    hits_in_slice: int
    slice_size: int

    @property
    def passed(self) -> bool:
        return self.factor >= self.threshold


def decoy_enrichment(
    results: list[DockingResult],
    actives: set[str],
    *,
    fraction: float,
    threshold: float,
) -> EnrichmentControl:
    """Dock the actives among the decoys and see where they land.

    Both ``fraction`` and ``threshold`` are passed in rather than defaulted.
    Enrichment at one per cent and at ten per cent are different claims, and a
    threshold with a default is a threshold nobody chose.
    """
    scored = [(result.ligand_id, result.top_score) for result in results]
    factor = enrichment_factor(scored, actives, fraction)

    ordered = sorted(scored, key=lambda item: (item[1], item[0]))
    slice_size = max(1, math.ceil(len(ordered) * fraction))
    hits = sum(1 for ligand, _ in ordered[:slice_size] if ligand in actives)

    return EnrichmentControl(
        fraction=fraction, factor=factor, threshold=threshold,
        actives=len(actives), decoys=len(ordered) - len(actives),
        hits_in_slice=hits, slice_size=slice_size,
    )
