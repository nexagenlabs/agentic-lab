"""The gold set, defined by a rule rather than by a size.

A random sample of twenty from a corpus at fourteen per cent prevalence
contains about three positives, and often fewer. Sensitivity computed on three
positives has a confidence interval wide enough to cover almost any claim, so
the set is enriched on purpose: every inclusion, every flag, every designed
case, and a fixed number of negatives drawn with a recorded seed.

The rule is the code below. The number it happens to produce is an output. If
a later build adds records to the corpus, the gold set grows with it, and the
alternative, a hard-coded size, would leave a reference standard that had
quietly stopped covering the corpus it claims to measure.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DECISIONS = ("include", "exclude", "flag")


class GoldSetError(RuntimeError):
    """The gold set cannot be built as specified."""


@dataclass(frozen=True)
class GoldSet:
    """An enriched reference standard, and the record of how it was drawn."""

    pmids: tuple[str, ...]
    labels: dict[str, str]
    inclusions: tuple[str, ...]
    flags: tuple[str, ...]
    designed: tuple[str, ...]
    seeded_negatives: tuple[str, ...]
    seed: int
    corpus_size: int
    criteria_version: int

    @property
    def size(self) -> int:
        return len(self.pmids)

    def label(self, pmid: str) -> str:
        return self.labels[pmid]

    def composition(self) -> dict[str, Any]:
        """Itemised, not summarised.

        The categories overlap: a designed case may also be an inclusion. The
        counts therefore do not sum to the total, and ``designed_also_counted
        _elsewhere`` says by how much, so a reader can see the arithmetic
        rather than suspect it.
        """
        enriched = set(self.inclusions) | set(self.flags) | set(self.designed)
        overlap = (
            len(self.inclusions) + len(self.flags) + len(self.designed) - len(enriched)
        )
        return {
            "total": self.size,
            "inclusions": len(self.inclusions),
            "flags": len(self.flags),
            "designed_cases": len(self.designed),
            "designed_also_counted_elsewhere": overlap,
            "seeded_negatives": len(self.seeded_negatives),
            "seed": self.seed,
            "corpus_size": self.corpus_size,
            "selection": (
                "Enriched by rule, not sampled: every inclusion, every flag "
                "and every designed case, plus a fixed number of negatives "
                "drawn with the recorded seed."
            ),
        }


def load_gold(path: str | Path) -> dict[str, Any]:
    """Read Build 03's ground truth file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("labels", "notes", "criteria_version"):
        if key not in data:
            raise GoldSetError(f"gold file is missing {key!r}: {path}")
    return data


def build_gold_set(gold: dict[str, Any], *, seed: int, negatives: int) -> GoldSet:
    """Apply the rule to a ground truth file.

    ``seed`` is required rather than defaulted. A caller that has to pass it is
    a caller that has it to record, which is the only way the draw can be
    reproduced later.
    """
    labels: dict[str, str] = dict(gold["labels"])
    notes: dict[str, Any] = dict(gold["notes"])

    unknown = {label for label in labels.values()} - set(DECISIONS)
    if unknown:
        raise GoldSetError(f"gold labels contain unknown decisions: {sorted(unknown)}")

    missing = sorted(set(notes) - set(labels))
    if missing:
        raise GoldSetError(f"designed cases with no label: {missing}")

    inclusions = tuple(sorted(p for p, label in labels.items() if label == "include"))
    flags = tuple(sorted(p for p, label in labels.items() if label == "flag"))
    designed = tuple(sorted(notes))

    if not inclusions:
        raise GoldSetError(
            "the corpus has no inclusions, so a gold set drawn from it could "
            "measure sensitivity only by dividing by zero"
        )

    # The negatives are drawn from what the enriched categories did not take,
    # so that the draw cannot silently re-select a record already included.
    enriched = set(inclusions) | set(flags) | set(designed)
    pool = sorted(set(labels) - enriched)
    if len(pool) < negatives:
        raise GoldSetError(
            f"cannot draw {negatives} negatives: only {len(pool)} records "
            "remain once inclusions, flags and designed cases are taken"
        )

    seeded = tuple(sorted(random.Random(seed).sample(pool, negatives)))

    # A union. A record that is both a designed case and an inclusion appears
    # once, which is what makes the counts overlap rather than double count.
    pmids = tuple(sorted(enriched | set(seeded)))

    return GoldSet(
        pmids=pmids,
        labels={pmid: labels[pmid] for pmid in pmids},
        inclusions=inclusions,
        flags=flags,
        designed=designed,
        seeded_negatives=seeded,
        seed=seed,
        corpus_size=len(labels),
        criteria_version=int(gold["criteria_version"]),
    )
