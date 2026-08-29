"""Screening statistics, in the order the chapter reports them.

Sensitivity first, because it is the only number that says what you lost.
Positive predictive value last, because it is the number most likely to be
quoted and least likely to mean what the reader thinks.

Accuracy is not here. It is refused, loudly, by a function that exists only to
explain why: on this corpus a screen that excluded every single record would
score above eighty-five per cent, and a metric that rewards doing nothing is
not a metric.

Two conventions are worth stating, because both are judgements the spec left
open and both change the numbers.

A flagged record is not lost. It goes to a human, which is where a record the
text cannot settle is supposed to go, so a flag on a true inclusion counts as
retained rather than as a miss. Counting it as a miss would punish the screen
for the one behaviour the criteria demand of it.

Agreement between the two screens is computed over all three decisions rather
than a collapsed pair, because a record one screen includes and the other
flags is a real disagreement and hiding it would flatter the statistic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

DECISIONS = ("include", "exclude", "flag")

# Landis and Koch, 1977. The bands are conventional rather than principled,
# which is exactly why the word must travel with the number: a reader who sees
# 0.47 alone will invent their own band.
LANDIS_KOCH = (
    (0.00, "poor"),
    (0.20, "slight"),
    (0.40, "fair"),
    (0.60, "moderate"),
    (0.80, "substantial"),
    (1.01, "almost perfect"),
)

ACCURACY_REFUSAL = (
    "Accuracy is not computed by this build, deliberately. At the prevalence "
    "of a screening corpus, a screen that excluded every record without "
    "reading any of them would score above eighty-five per cent accuracy, "
    "which makes the number worse than useless: it is actively misleading to "
    "anyone who has not checked the prevalence first. Report sensitivity, "
    "which says what you lost, and specificity, which says what it cost you. "
    "If you need one number for a summary table, use sensitivity."
)


class MetricRefused(RuntimeError):
    """A metric this build declines to compute, with the reason."""


class MetricError(RuntimeError):
    """The inputs cannot support the metric requested."""


def accuracy(*args: Any, **kwargs: Any) -> float:
    """Refuse, and say why. Never returns."""
    raise MetricRefused(ACCURACY_REFUSAL)


def kappa_band(value: float) -> str:
    """The Landis and Koch word for a kappa, so the number travels with it."""
    if value < 0:
        return "poor"
    for upper, word in LANDIS_KOCH:
        if value < upper:
            return word
    return "almost perfect"


def retained(decision: str) -> bool:
    """Whether a decision keeps a record in play.

    Include and flag both do: one goes forward, the other goes to a person.
    Only an exclusion removes a record from the review, which is why only an
    exclusion can lose a true inclusion.
    """
    return decision in ("include", "flag")


@dataclass
class ScreenPerformance:
    """One screen measured against the gold set."""

    true_positives: int
    false_negatives: int
    true_negatives: int
    false_positives: int
    gold_size: int
    lost: tuple[str, ...] = field(default_factory=tuple)

    @property
    def sensitivity(self) -> float:
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            raise MetricError("no gold inclusions, so sensitivity is undefined")
        return self.true_positives / denominator

    @property
    def specificity(self) -> float:
        denominator = self.true_negatives + self.false_positives
        if denominator == 0:
            raise MetricError("no gold negatives, so specificity is undefined")
        return self.true_negatives / denominator

    @property
    def negative_predictive_value(self) -> float:
        denominator = self.true_negatives + self.false_negatives
        if denominator == 0:
            raise MetricError("the screen excluded nothing, so NPV is undefined")
        return self.true_negatives / denominator

    @property
    def positive_predictive_value(self) -> float:
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            raise MetricError("the screen retained nothing, so PPV is undefined")
        return self.true_positives / denominator

    def as_dict(self) -> dict[str, Any]:
        """Reported in the chapter's order, not alphabetically."""
        return {
            "sensitivity": self.sensitivity,
            "specificity": self.specificity,
            "negative_predictive_value": self.negative_predictive_value,
            "positive_predictive_value": self.positive_predictive_value,
            "true_positives": self.true_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "gold_size": self.gold_size,
            "records_lost": list(self.lost),
        }


def score_against_gold(
    decisions: dict[str, str], gold_labels: dict[str, str]
) -> ScreenPerformance:
    """Measure one screen against the gold set.

    ``decisions`` may cover more records than the gold set. Only the gold
    records are scored, because they are the only ones whose answer is known.
    """
    missing = sorted(set(gold_labels) - set(decisions))
    if missing:
        raise MetricError(f"screen has no verdict for gold records: {missing}")

    tp = fn = tn = fp = 0
    lost: list[str] = []
    for pmid, truth in gold_labels.items():
        kept = retained(decisions[pmid])
        if truth == "include":
            if kept:
                tp += 1
            else:
                fn += 1
                lost.append(pmid)
        elif kept:
            fp += 1
        else:
            tn += 1

    return ScreenPerformance(tp, fn, tn, fp, len(gold_labels), tuple(sorted(lost)))


@dataclass
class Agreement:
    """Two screens measured against each other."""

    observed: float
    kappa: float
    pabak: float
    ac1: float
    n: int
    categories: tuple[str, ...]

    @property
    def band(self) -> str:
        return kappa_band(self.kappa)

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_agreement": self.observed,
            "kappa": self.kappa,
            "kappa_band": self.band,
            "pabak": self.pabak,
            "ac1": self.ac1,
            "n": self.n,
            "categories": list(self.categories),
        }


def agreement(
    a: dict[str, str], b: dict[str, str], categories: tuple[str, ...] = DECISIONS
) -> Agreement:
    """Observed agreement, Cohen's kappa, PABAK and Gwet's AC1.

    All three chance-corrected statistics answer the same question and
    disagree because they model chance differently. Kappa assumes the two
    screens guess independently at their own observed rates, which at low
    prevalence makes chance agreement enormous and drags kappa down. PABAK
    assumes uniform marginals. AC1 weights each category by how hard it is to
    guess. Reporting one alone invites the reader to believe it.
    """
    shared = sorted(set(a) & set(b))
    if not shared:
        raise MetricError("the two screens share no records")

    disagreed = sorted(set(a) ^ set(b))
    if disagreed:
        raise MetricError(
            f"the two screens cover different records: {disagreed[:5]}"
        )

    n = len(shared)
    observed = sum(1 for pmid in shared if a[pmid] == b[pmid]) / n

    count_a = Counter(a[pmid] for pmid in shared)
    count_b = Counter(b[pmid] for pmid in shared)

    # Cohen: chance is each screen drawing independently at its own rate.
    expected = sum((count_a[c] / n) * (count_b[c] / n) for c in categories)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0

    # PABAK: chance is a uniform draw across the categories in play.
    k = len(categories)
    pabak = (k * observed - 1) / (k - 1)

    # Gwet: chance weighted by how hard each category is to guess.
    pi = {c: (count_a[c] / n + count_b[c] / n) / 2 for c in categories}
    expected_gwet = sum(p * (1 - p) for p in pi.values()) / (k - 1)
    ac1 = (observed - expected_gwet) / (1 - expected_gwet)

    return Agreement(observed, kappa, pabak, ac1, n, tuple(categories))
