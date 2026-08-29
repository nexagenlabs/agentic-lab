"""The refusal. As with ``accuracy`` in Build 04, refusing is stronger than
omitting.

If this module simply had no affinity function, a reader would write one. The
function exists, it is importable, it has the name somebody would reach for,
and it raises with the numbers that explain why. That is a check. An omission
is only an invitation.
"""

from __future__ import annotations

from typing import Any, NoReturn

REFUSAL = (
    "A docking score is a ranking, not a measurement, and this build will not "
    "convert one into an affinity. Score to affinity correlations run from "
    "0.10 to 0.38 across seven programs on roughly 1,300 complexes, and one "
    "benchmark recorded AutoDock Vina at minus 0.18, which is to say worse "
    "than nothing. Absolute predictions carry 1.5 to 2.0 log units of error, "
    "so a Kd reported from a docking score is uncertain by a factor of "
    "thirty to a hundred. What docking supports is enrichment: given a "
    "library, it puts more actives near the top than chance would. Rank the "
    "library, take the top of it to an assay, and report the score as a rank."
)


class AffinityClaimRefused(RuntimeError):
    """A structured refusal, carrying a code like every other error here."""

    def __init__(self, quantity: str) -> None:
        super().__init__(f"affinity_claim_refused: {quantity}. {REFUSAL}")
        self.code = "affinity_claim_refused"
        self.quantity = quantity

    def as_dict(self) -> dict[str, str]:
        return {"status": "REFUSED", "code": self.code,
                "quantity": self.quantity, "detail": REFUSAL}


def predicted_kd(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Refuses. See ``REFUSAL``."""
    raise AffinityClaimRefused("Kd")


def predicted_ki(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Refuses. See ``REFUSAL``."""
    raise AffinityClaimRefused("Ki")


def predicted_binding_affinity(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Refuses. See ``REFUSAL``."""
    raise AffinityClaimRefused("binding affinity")


def score_to_affinity(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Refuses. See ``REFUSAL``."""
    raise AffinityClaimRefused("affinity converted from a docking score")


AFFINITY_METHODS = (
    predicted_kd,
    predicted_ki,
    predicted_binding_affinity,
    score_to_affinity,
)
