"""The smallest piece of code in the chapter with the largest effect.

Chapter 7's failure account: four isoforms got four boxes over four days, each
box drawn sensibly on its own morning, and the numbers were not comparable to
each other. Nobody made a mistake. There was simply nothing in the pipeline
that knew the four runs were meant to be one comparison.

A comparison set is that thing. Every box in it must use the same strategy,
and a set built from two strategies does not get made.
"""

from __future__ import annotations

from dataclasses import dataclass

from models import DockingBox


class ComparisonSetRefused(RuntimeError):
    """A structured refusal, carrying the code that names the reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class ComparisonSet:
    """Boxes for a set of targets that are going to be compared."""

    comparison_set_id: str
    boxes: dict[str, DockingBox]

    @property
    def strategy(self) -> str:
        return next(iter(self.boxes.values())).strategy


def build_comparison_set(
    comparison_set_id: str, boxes: dict[str, DockingBox]
) -> ComparisonSet:
    """Construct a set, or refuse. There is no way to build a mixed one."""
    if not boxes:
        raise ComparisonSetRefused(
            "empty_set", "a comparison set with no boxes compares nothing"
        )

    wrong_id = sorted(
        target for target, box in boxes.items()
        if box.comparison_set_id != comparison_set_id
    )
    if wrong_id:
        raise ComparisonSetRefused(
            "wrong_comparison_set",
            f"these boxes name a different comparison set: {wrong_id}. A box "
            "belongs to the comparison it was drawn for.",
        )

    strategies = {box.strategy for box in boxes.values()}
    if len(strategies) > 1:
        by_strategy = {
            strategy: sorted(t for t, b in boxes.items() if b.strategy == strategy)
            for strategy in sorted(strategies)
        }
        raise ComparisonSetRefused(
            "mixed_box_strategies",
            f"comparison set {comparison_set_id!r} mixes box strategies: "
            f"{by_strategy}. A box placed on a co-crystallised ligand and a "
            "box placed on a residue list are not the same question asked "
            "twice, and scores from them do not belong in one table. Pick one "
            "strategy for the set and redraw the others.",
        )

    return ComparisonSet(comparison_set_id=comparison_set_id, boxes=dict(boxes))
