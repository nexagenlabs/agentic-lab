"""Distances between poses, taken in Python.

Two numbers come out of this file and both are arithmetic. The redocking RMSD
says whether the setup can recover an answer it already knows, and the cluster
occupancy says whether a top score is supported by anything.

Atoms are compared in the order the engine wrote them, which is the order they
appear in the ligand file. That is correct for a redock, where both poses are
the same molecule written the same way, and it is deliberately not a symmetry
corrected RMSD: a symmetry aware comparison is a real requirement for a
symmetric ligand and it is a larger piece of code than this chapter has room
for. The limit is stated rather than hidden, which is the rule everywhere here.
"""

from __future__ import annotations

import math

Coordinates = list[tuple[float, float, float]]


class GeometryError(RuntimeError):
    """Two things that cannot be compared."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def rmsd(first: Coordinates, second: Coordinates) -> float:
    """Root mean square deviation, atom by atom, in angstroms."""
    if len(first) != len(second):
        raise GeometryError(
            "atom_count_mismatch",
            f"{len(first)} atoms against {len(second)}. These are not the "
            "same molecule, or not written the same way.",
        )
    if not first:
        raise GeometryError("no_atoms", "an empty pose has no geometry")

    total = 0.0
    for (x1, y1, z1), (x2, y2, z2) in zip(first, second, strict=True):
        total += (x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2
    return math.sqrt(total / len(first))


def cluster_occupancy(poses, cutoff_angstrom: float = 2.0) -> int:
    """How many poses sit within ``cutoff`` of the best scoring one.

    This is the number that separates a top score worth acting on from one
    that is not. A search that converged on a binding mode returns it several
    times over; a search that returned it once found a corner of the box it
    liked and nothing agrees with it. Both report the same top score.
    """
    if not poses:
        raise GeometryError("no_poses", "an empty result has no distribution")
    best = min(poses, key=lambda pose: (pose.score, pose.rank))
    return sum(
        1 for pose in poses
        if rmsd(best.coordinates, pose.coordinates) <= cutoff_angstrom
    )


def spread(poses) -> float:
    """The largest distance between any pose and the best scoring one."""
    best = min(poses, key=lambda pose: (pose.score, pose.rank))
    return max(rmsd(best.coordinates, pose.coordinates) for pose in poses)
