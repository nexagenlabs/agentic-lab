"""Table 12.3, as refusals rather than omissions.

Build 04 exports ``accuracy`` and raises. Build 08 exports ``predicted_kd`` and
raises. The argument is the same both times and it is worth restating once
more, because this is the last build and it is the one somebody will extend.

A module with no ``generate_hypothesis`` function is an invitation to write
one. The absence looks like an oversight, the name looks obvious, and the
person adding it is under time pressure and has no idea there was an argument.
A module that exports ``generate_hypothesis`` and raises with three sentences
saying why is a conversation with that person at the moment they need it.

Grep for ``NotThisSystem`` to find every one of them.

What the desk does not do:

    generate_hypothesis     it retrieves and ranks what exists. A ranking is
                            not a hypothesis and the difference is the whole
                            of the reader's job.
    is_promising            "interesting" is a judgement about what your
                            laboratory can do next, which nothing here knows.
    predicted_affinity      a docking score is a ranking, not a measurement.
    novel_claim             every sentence the desk emits is traceable to a
                            record it read. A novel claim by definition is not.
    decide                  the three checkpoints exist because the decisions
                            belong to a person.
    rank_by_confidence      the desk has no calibrated confidence to rank by,
                            and a number that looks like one is worse than
                            none.
"""

from __future__ import annotations

from typing import Any, NoReturn


class NotThisSystem(RuntimeError):
    """A capability this system deliberately does not have.

    Raised rather than omitted, so the refusal is discoverable from the code
    rather than from the documentation nobody read.
    """

    def __init__(self, capability: str, why: str) -> None:
        super().__init__(f"{capability}: {why}")
        self.capability = capability
        self.why = why
        self.code = "not_this_system"

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code,
                "capability": self.capability, "why": self.why}


def generate_hypothesis(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "generate_hypothesis",
        "This desk retrieves what has been published, screens it against "
        "criteria somebody wrote down, docks what survives and ranks the "
        "result. Every one of those is a search over things that already "
        "exist. A hypothesis is a claim about what is true that nobody has "
        "made yet, and nothing in this pipeline is capable of making one. The "
        "shortlist is where your work starts, not where it finishes.",
    )


def is_promising(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "is_promising",
        "Whether a candidate is worth pursuing depends on what your "
        "laboratory can actually run next month, what the compound costs, who "
        "has worked on it before, and what your group is trying to find out. "
        "None of that is in this system. A function returning True here would "
        "be the desk making a resourcing decision on your behalf while "
        "looking like an assay result.",
    )


def predicted_affinity(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "predicted_affinity",
        "A docking score is a ranking, not a measurement. Score to affinity "
        "correlations run from 0.10 to 0.38 across seven programs on roughly "
        "1,300 complexes. Absolute predictions carry 1.5 to 2.0 log units of "
        "error, which is a factor of thirty to a hundred on a Kd. Build 08 "
        "refuses this for the same reason and with the same numbers.",
    )


def novel_claim(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "novel_claim",
        "Every sentence this desk emits is traceable to a record it read, a "
        "score it parsed or a criterion somebody wrote. That traceability is "
        "the only reason its output can be checked. A claim that is novel is "
        "by construction not traceable to any of them, and emitting one would "
        "put an unsourced sentence inside a provenance trail, which is worse "
        "than emitting it with no trail at all.",
    )


def decide(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "decide",
        "The three checkpoints exist because three decisions in this pipeline "
        "belong to a person: what to read in full, what to spend compute on, "
        "and what to take to a bench. A decide() that made them would not be "
        "an improvement to the desk, it would be the removal of the only part "
        "of it that has any authority.",
    )


def rank_by_confidence(*_: Any, **__: Any) -> NoReturn:
    raise NotThisSystem(
        "rank_by_confidence",
        "Nothing here produces a calibrated confidence. The screening stub "
        "emits high and low, which are labels rather than probabilities, and "
        "no part of this repository has ever measured whether a high is right "
        "more often than a low. A number that looks like a confidence and is "
        "not one is worse than no number, because it will be averaged.",
    )


# Every refusal, so a test can walk them rather than listing them again.
REFUSALS = {
    "generate_hypothesis": generate_hypothesis,
    "is_promising": is_promising,
    "predicted_affinity": predicted_affinity,
    "novel_claim": novel_claim,
    "decide": decide,
    "rank_by_confidence": rank_by_confidence,
}
