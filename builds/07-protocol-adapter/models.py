"""The adapted protocol is not the product. The diff is.

Chapter 6's failure account is an adapter that changed the concentrations it
was asked about and silently kept the seeding density and the endpoint it was
not. The wells went confluent, the dynamic range compressed, the IC50 came out
about twofold wrong, and every check the adapter ran passed. Nothing in that
account is a bug in the model. The bug is that the output had no place to
record what the adapter had not thought about.

So the four lists below are the build. ``changed`` is the easy one and the
least interesting. ``carried_over_unchanged`` is dangerous because a parameter
kept on purpose and a parameter kept by inattention look identical once the
protocol is printed. ``not_stated_in_source`` is worse again, because it is
the set of things nobody can check.

Every parameter in Table 6.2 must land in exactly one of the four, and that is
enforced here as a validator rather than asked for in a prompt. A prompt
instruction is a request. A validator is a refusal, and this one cannot be
talked out of it by a model having a bad day.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Table 6.2. Silence about any of these is an error, not a default.
MANDATORY_PARAMETERS: tuple[str, ...] = (
    "seeding_density",
    "incubation_to_endpoint",
    "solvent_tolerance",
    "passage_number_range",
    "serum_concentration",
    "readout_chemistry",
)

RRID_PATTERN = r"^CVCL_[A-Z0-9]{4}$"


class AdapterError(RuntimeError):
    """A structured refusal, never prose returned into a model's context."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"status": "ERROR", "code": self.code, "detail": self.detail}


class TargetLine(BaseModel):
    """A cell line as a record, not a name.

    Identity again, as in Build 06: the RRID is required because a name is a
    label and labels have been wrong. The doubling time is required because
    without it the seeding density cannot be adapted, and an adapter that
    cannot adapt it must say so rather than carry it over.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    rrid: str = Field(pattern=RRID_PATTERN)
    doubling_time_h: float = Field(gt=0)
    serum_pct: float = Field(ge=0)
    max_dmso_pct: float = Field(gt=0)
    max_passage: int = Field(gt=0)
    # Readout chemistries this line is known to interfere with. A metabolic
    # dye against a line with unusual reductase activity is not a decision an
    # adapter makes on your behalf.
    assay_interference: list[str] = Field(default_factory=list)


class ExtractedParameter(BaseModel):
    """One Table 6.2 parameter, as read out of the source protocol.

    ``evidence`` is the quoted sentence the value was read from, and it is
    checked against the protocol text rather than believed. A value with no
    quotable evidence is not a value, it is the adapter filling a gap.
    """

    model_config = ConfigDict(extra="forbid")

    parameter: str
    stated: bool
    value: str | None = None
    evidence: str | None = None


class ParameterChange(BaseModel):
    parameter: str
    source_value: str            # what the paper said
    adapted_value: str           # what we will do
    rationale: str
    confidence: Literal["high", "low"]


class Adaptation(BaseModel):
    source_doi: str
    source_cell_line: str
    target_cell_line: str
    changed: list[ParameterChange]
    carried_over_unchanged: list[str]     # the dangerous list
    not_stated_in_source: list[str]       # the more dangerous list
    requires_human_decision: list[str]

    @model_validator(mode="after")
    def every_mandatory_parameter_is_classified(self) -> Adaptation:
        """Exactly one list each, for all six. No silence, no double counting.

        This is deliberately not a prompt instruction. An adapter that reports
        only what it changed lets a reader walk into everything it did not
        consider, and the way to stop that is to make the object refuse to
        exist rather than to ask a model nicely.
        """
        placement: dict[str, list[str]] = {name: [] for name in MANDATORY_PARAMETERS}
        unknown: list[str] = []

        lists = {
            "changed": [change.parameter for change in self.changed],
            "carried_over_unchanged": self.carried_over_unchanged,
            "not_stated_in_source": self.not_stated_in_source,
            "requires_human_decision": self.requires_human_decision,
        }
        for list_name, parameters in lists.items():
            for parameter in parameters:
                if parameter in placement:
                    placement[parameter].append(list_name)
                else:
                    unknown.append(f"{parameter!r} in {list_name}")

        missing = sorted(p for p, where in placement.items() if not where)
        twice = sorted(
            f"{p} in {', '.join(where)}"
            for p, where in placement.items() if len(where) > 1
        )

        problems = []
        if missing:
            problems.append(
                "these Table 6.2 parameters appear in none of the four lists, "
                f"and silence about them is an error rather than a default: "
                f"{missing}"
            )
        if twice:
            problems.append(
                f"these parameters appear in more than one list: {twice}"
            )
        if unknown:
            problems.append(
                "these are not Table 6.2 parameters, so they are most likely "
                f"misspellings of one that is now missing: {sorted(unknown)}"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def as_dict(self) -> dict[str, object]:
        """The diff, for the run manifest and for the report."""
        return {
            "status": "OK",
            "source_doi": self.source_doi,
            "source_cell_line": self.source_cell_line,
            "target_cell_line": self.target_cell_line,
            "changed": [change.model_dump() for change in self.changed],
            "carried_over_unchanged": sorted(self.carried_over_unchanged),
            "not_stated_in_source": sorted(self.not_stated_in_source),
            "requires_human_decision": sorted(self.requires_human_decision),
        }
