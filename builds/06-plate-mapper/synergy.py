"""The synergy model is a claim, and the build refuses to make it for you.

Chapter 6 opens with an admission: the matrices were run, and the synergy
model was chosen after the surfaces were seen. Four candidate models plus a
post-hoc choice is four chances at a positive number, and nothing in the
resulting figure records that the choice was made last.

So ``choose_synergy_model`` raises. Not warns, not defaults, not picks the
most common one. The model encodes a mechanistic claim about how two agents
interact, and that claim belongs to a person who can defend it in review.
"""

from __future__ import annotations

MODELS = ("bliss", "loewe", "hsa", "zip")

REFUSAL = (
    "This build will not choose a synergy model for you, and the refusal is "
    "the feature. The model is a mechanistic claim: Bliss assumes the two "
    "agents act independently and multiply, Loewe assumes they share a "
    "dose-equivalence relationship, HSA claims only that the combination "
    "beats the better single agent, and ZIP interpolates between Bliss and "
    "Loewe. Those are different statements about biology and only one of them "
    "is yours to make.\n\n"
    "Choosing after the surfaces are drawn turns four candidate models into "
    "four chances at a positive result, and leaves no trace of having done "
    "so: not in the analysis, not in the figure, not in the manuscript. Write "
    "the model and a mechanistic justification into the design file, commit "
    "it before the plate is read, and this build will check the timestamp."
)

CONSENSUS_REFUSAL = (
    "Bliss and ZIP are not independent evidence and a consensus across both "
    "double-counts one assumption. ZIP is constructed by interpolating "
    "between the Bliss and Loewe reference models, so a ZIP score already "
    "contains the Bliss claim. SynergyFinder excludes ZIP from its consensus "
    "score for exactly this reason. Pick one, or build the consensus from "
    "models that rest on different assumptions."
)


class SynergyModelRefused(RuntimeError):
    """This build declines to choose, and says why."""


class ConsensusRefused(RuntimeError):
    """The requested consensus double-counts an assumption."""


def choose_synergy_model(*args: object, **kwargs: object) -> str:
    """Refuse, and explain. Never returns."""
    raise SynergyModelRefused(REFUSAL)


def check_consensus(models: list[str] | tuple[str, ...] | set[str]) -> None:
    """Reject a consensus set that is not independent evidence."""
    requested = {model.strip().lower() for model in models}

    unknown = sorted(requested - set(MODELS))
    if unknown:
        raise ConsensusRefused(
            f"unknown synergy models: {unknown}. Known models are "
            f"{', '.join(MODELS)}."
        )

    if {"bliss", "zip"} <= requested:
        raise ConsensusRefused(CONSENSUS_REFUSAL)

    if len(requested) < 2:
        raise ConsensusRefused(
            "a consensus needs at least two models resting on different "
            "assumptions; one model is not a consensus"
        )
