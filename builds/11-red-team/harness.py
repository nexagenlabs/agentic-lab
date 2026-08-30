"""The positive control the agents in this repository do not otherwise have.

Every wet-lab assay in this book has controls. Until this build, no agent here
had been run on an input designed to make it fail in a known way, which means
no claim about any of them had a denominator.

Three things in this file carry more weight than their size suggests.

**``silent``.** A fault that is missed but crashes the run is a nuisance:
somebody sees a traceback and looks. A fault that is missed while the run
completes normally, returns a plausible answer and writes a clean manifest is
the category this entire book is about, and it is the only number on the report
worth losing sleep over. ``Report`` counts and reports the two separately and
refuses to add them together.

**The denominator, always.** ``Report.summary()`` returns "n of m, across k
families" and there is no method anywhere that returns a bare fraction. A
detection rate of 1.0 is a statement about the faults somebody thought of, and
printed without its denominator it reads as a statement about the system.

**The family lives in the fault id.** The printed ``FaultResult`` constructor
below takes four arguments and family is not one of them, so a result cannot
carry a family of its own. Fault identifiers are therefore ``<family>-<n>`` and
``Report`` parses them. That is a consequence of the listing rather than a
preference, and it is written down here so the next person does not decide it
was an accident.

The chapter names four families. There is a fifth, ``identity``, and it is not
in the ``Literal`` below because the ``Literal`` below is what the book prints.
It lives in ``families.py``, for the reason the chapter's own failure account
gives: a harness scored 1.0 across thirty-one faults and missed a preprint
counted twice, because nobody had conceived of the family it belonged to. A
fixed enum is the data structure version of that mistake.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class FaultResult(BaseModel):
    """One planted fault and what the pipeline did about it.

    ``silent`` is the field that matters. Caught is good news, missed and
    crashed is bad news somebody will notice, and missed while COMPLETE is the
    case where a wrong answer went downstream wearing a clean manifest.
    """

    model_config = ConfigDict(extra="forbid")

    fault_id: str
    caught: bool
    fired: list[str]
    silent: bool

    @property
    def family(self) -> str:
        """Parsed from the identifier, because the constructor has no field
        for it and the printed listing is not going to grow one."""
        return self.fault_id.split("-", 1)[0]


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[FaultResult]

    @property
    def caught(self) -> int:
        return sum(1 for result in self.results if result.caught)

    @property
    def missed(self) -> list[FaultResult]:
        return [result for result in self.results if not result.caught]

    @property
    def silent_misses(self) -> list[FaultResult]:
        """Missed, and the run finished normally. The book's whole subject."""
        return [result for result in self.results if result.silent]

    @property
    def families(self) -> list[str]:
        return sorted({result.family for result in self.results})

    def rate(self) -> tuple[int, int]:
        """Always a pair. There is deliberately no method returning a float."""
        return self.caught, len(self.results)

    def rate_for(self, family: str) -> tuple[int, int]:
        subset = [r for r in self.results if r.family == family]
        return sum(1 for r in subset if r.caught), len(subset)

    def summary(self) -> str:
        caught, total = self.rate()
        return (f"{caught} of {total}, across {len(self.families)} families; "
                f"{len(self.silent_misses)} silent")

    def combined(self, other: Report) -> Report:
        return Report(results=self.results + other.results)

    def as_dict(self) -> dict[str, Any]:
        """Everything, including the failures. A harness that reported only
        its successes would be this chapter's failure one level up."""
        return {
            "status": "MEASURED",
            "code": "red_team_complete",
            "summary": self.summary(),
            "caught": self.caught,
            "planted": len(self.results),
            "silent_misses": [r.fault_id for r in self.silent_misses],
            "missed": [r.fault_id for r in self.missed],
            "by_family": {
                family: {"caught": self.rate_for(family)[0],
                         "planted": self.rate_for(family)[1]}
                for family in self.families
            },
            "results": [r.model_dump() for r in self.results],
        }


class Fault(BaseModel):
    fault_id: str
    family: Literal["fabrication", "numeric", "drift", "loop"]
    description: str
    inject: Callable[[Any], Any]      # corrupts the input
    should_be_caught_by: str          # the check you expect to fire

def run_red_team(pipeline, faults: list[Fault], clean_input) -> Report:
    results = []
    for fault in faults:
        corrupted = fault.inject(deepcopy(clean_input))
        outcome = pipeline.run(corrupted)
        caught = fault.should_be_caught_by in outcome.checks_fired
        results.append(FaultResult(
            fault_id=fault.fault_id, caught=caught,
            fired=outcome.checks_fired,
            silent=not caught and outcome.status == "COMPLETE"))
    return Report(results=results)
