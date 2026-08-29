"""Ranking, and the two things a ranking is not allowed to do.

It is not allowed to mix provenance without saying so. Docking to as-is
predicted models performed consistently worse than to experimental holo
structures across twenty-two targets, with enrichment factors of zero on
several, so a table that sorts one against the other is comparing a number
that means one thing against a number that means another. That is Chapter 2's
failure, and it is fixed here structurally rather than by remembering.

And it is not allowed to become an affinity. See ``affinity.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from models import DockingResult, StructureRecord


class RankingRefused(RuntimeError):
    """A structured refusal, carrying the code that names the reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class RankedEntry:
    """One row of a ranking, with where its structure came from attached."""

    position: int
    ligand_id: str
    target: str
    score: float
    source: str
    ligand_state: str
    cluster_occupancy: int | None = None


def rank_results(
    results: list[DockingResult],
    records: dict[str, StructureRecord],
    *,
    allow_mixed_provenance: bool = False,
) -> list[RankedEntry]:
    """Sort by top score, refusing a mixed set unless told explicitly."""
    missing = sorted({r.target for r in results} - set(records))
    if missing:
        raise RankingRefused(
            "no_provenance",
            f"no structure record for {missing}. A score with no record of "
            "which structure produced it is not evidence about anything.",
        )

    sources = {records[result.target].source for result in results}
    if len(sources) > 1 and not allow_mixed_provenance:
        raise RankingRefused(
            "mixed_provenance",
            "this set contains both EXPERIMENTAL and PREDICTED structures. "
            "Docking to as-is predicted models performed consistently worse "
            "than to experimental holo structures across twenty-two targets, "
            "with enrichment factors of zero on several, so the two columns "
            "are not the same measurement. Pass "
            "allow_mixed_provenance=True if you mean it; the flag is written "
            "to the manifest.",
        )

    ordered = sorted(results, key=lambda r: (r.top_score, r.ligand_id))
    return [
        RankedEntry(
            position=position,
            ligand_id=result.ligand_id,
            target=result.target,
            score=result.top_score,
            source=records[result.target].source,
            ligand_state=records[result.target].ligand_state,
        )
        for position, result in enumerate(ordered, start=1)
    ]


def consensus_rank(rankings: dict[str, list[str]]) -> list[tuple[str, float]]:
    """Aggregate several scoring functions into one order.

    What this does and does not do, plainly. Averaging ranks across scoring
    functions reduces the variance of a ranking: a compound that one function
    likes for an idiosyncratic reason falls back towards where the others put
    it, and the top of the list becomes less sensitive to which program you
    happened to run. That is worth having.

    It does not turn a ranking into an affinity. The consensus of several
    weakly correlated scores is still a ranking, and the correlations being
    aggregated run from 0.10 to 0.38. A more stable ordering of numbers that
    do not measure binding energy is a more stable ordering, nothing more.
    """
    if len(rankings) < 2:
        raise RankingRefused(
            "consensus_of_one",
            "a consensus over one scoring function is that scoring function. "
            "Pass at least two.",
        )

    ligands = set.intersection(*(set(order) for order in rankings.values()))
    if not ligands:
        raise RankingRefused(
            "no_common_ligands",
            "the rankings share no ligand, so there is nothing to aggregate",
        )

    mean_rank = {
        ligand: sum(order.index(ligand) + 1 for order in rankings.values())
        / len(rankings)
        for ligand in ligands
    }
    return sorted(mean_rank.items(), key=lambda item: (item[1], item[0]))


def enrichment_factor(
    scored: list[tuple[str, float]],
    actives: set[str],
    fraction: float,
) -> float:
    """Actives in the top slice, over actives you would get by chance.

    This is the claim docking supports, so it is the number the campaign
    reports. ``fraction`` is passed in rather than defaulted, because the
    enrichment factor at one per cent and at ten per cent are different
    claims and a default hides which one is being made.
    """
    if not 0 < fraction <= 1:
        raise RankingRefused(
            "bad_fraction", f"fraction must be in (0, 1], got {fraction}"
        )
    if not scored:
        raise RankingRefused("empty_library", "nothing was scored")
    if not actives:
        raise RankingRefused(
            "no_actives",
            "enrichment against a library with no known actives is not "
            "computable, and a number reported for it would be fiction",
        )

    ordered = sorted(scored, key=lambda item: (item[1], item[0]))
    top_n = max(1, math.ceil(len(ordered) * fraction))
    hits = sum(1 for ligand, _ in ordered[:top_n] if ligand in actives)
    baseline = len(actives) / len(ordered)
    return (hits / top_n) / baseline
