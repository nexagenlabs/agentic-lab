"""The design is a declaration, and it comes first.

Everything the plate needs is in the YAML: the line and its identifier, both
dose axes, the controls, the edge policy, the replication, the randomisation
seed, and the analysis commitment. Nothing is decided later and nothing is
implicit.

The RRID is the part people argue about. A commercial authentication service
found 4.7 per cent of submitted lines misidentified in 2024 and 2.4 per cent
in 2025. ``U87MG`` is a label, and labels have been wrong; ``CVCL_0022`` is an
identifier that can be checked. A design that names a line without one is
rejected here rather than discussed later.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

RRID_PATTERN = r"^CVCL_[A-Z0-9]{4}$"


class DesignError(RuntimeError):
    """The design cannot be used as written."""

    def __init__(self, failure: str, detail: str) -> None:
        super().__init__(f"{failure}: {detail}")
        self.failure = failure
        self.detail = detail


class Axis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    top_conc_uM: float = Field(gt=0)
    dilution_factor: float = Field(gt=1)
    n_steps: int = Field(ge=2, le=24)

    def series_uM(self) -> list[float]:
        """The concentrations this axis actually delivers."""
        return [self.top_conc_uM / (self.dilution_factor ** i)
                for i in range(self.n_steps)]


class VehicleControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wells: int = Field(ge=1)
    solvent: str = Field(min_length=1)
    final_pct: float = Field(gt=0)


class PlainControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wells: int = Field(ge=1)


class Controls(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle: VehicleControl
    untreated: PlainControl
    blank: PlainControl

    @property
    def total(self) -> int:
        return self.vehicle.wells + self.untreated.wells + self.blank.wells


class Analysis(BaseModel):
    """The synergy commitment, made before any data exists."""

    model_config = ConfigDict(extra="forbid")

    synergy_model: str = Field(min_length=1)
    justification: str = Field(min_length=40)
    committed_at: datetime

    @field_validator("justification")
    @classmethod
    def justification_must_be_mechanistic(cls, value: str) -> str:
        """A justification that says nothing is not a justification.

        The length floor is crude and deliberate. The point is not that forty
        characters proves anything, it is that a person who has to write a
        sentence has to have a reason, and "bliss" on its own is not one.
        """
        if len(value.split()) < 8:
            raise ValueError(
                "justification must be a written mechanistic argument, not a "
                "restatement of the model name"
            )
        return value


class Design(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str = Field(min_length=1)
    cell_line: str = Field(min_length=1)
    rrid: str | None = None
    seeding_density: int = Field(gt=0)
    plate_format: Literal[96, 384]
    axes: dict[str, Axis]
    controls: Controls
    edge_policy: Literal["exclude_perimeter", "use_all"]
    replicates: int = Field(ge=1, le=12)
    # The serial transfer volume, where the design states one. None means the
    # design is silent and the bench parameter comes from the caller: a
    # default invented here would be a pipetting decision nobody wrote down.
    transfer_uL: float | None = Field(default=None, gt=0)
    randomise_within_plate: bool
    randomisation_seed: int = 20260314
    analysis: Analysis | None = None

    @property
    def rows(self) -> int:
        return 8 if self.plate_format == 96 else 16

    @property
    def columns(self) -> int:
        return 12 if self.plate_format == 96 else 24

    @property
    def combinations(self) -> int:
        total = 1
        for axis in self.axes.values():
            total *= axis.n_steps
        return total

    @property
    def treatment_wells(self) -> int:
        return self.combinations * self.replicates


def validate_design(design: Design) -> None:
    """Every refusal this build makes about a design, in one place."""
    if not design.rrid:
        raise DesignError(
            "no_rrid",
            f"the design names cell line {design.cell_line!r} with no RRID. "
            "A name is a label and labels have been wrong: an authentication "
            "service found 4.7 per cent of submitted lines misidentified in "
            "2024. Add the Cellosaurus identifier, for example CVCL_0022.",
        )

    if not re.match(RRID_PATTERN, design.rrid):
        raise DesignError(
            "malformed_rrid",
            f"{design.rrid!r} is not a Cellosaurus identifier; expected the "
            f"form CVCL_0022",
        )

    if design.analysis is None:
        raise DesignError(
            "no_synergy_model",
            "the design commits to no synergy model. The model encodes a "
            "mechanistic claim about how the two agents interact, and running "
            "the matrix first and choosing afterwards is how four candidate "
            "models become four chances at a positive number.",
        )

    if len(design.axes) != 2:
        raise DesignError(
            "wrong_axis_count",
            f"a combination design needs exactly two axes, got {len(design.axes)}",
        )


def load_design(path: str | Path) -> Design:
    """Read and validate a design, or raise ``DesignError``."""
    path = Path(path)
    try:
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise DesignError("unreadable", f"{path}: {error}") from error

    if not isinstance(body, dict):
        raise DesignError("unreadable", f"{path} is not a mapping")

    try:
        design = Design(**body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        failure = "no_synergy_model" if location.startswith("analysis") else "schema"
        raise DesignError(failure, f"{location}: {first['msg']}") from error

    validate_design(design)
    return design


def design_as_dict(design: Design) -> dict[str, Any]:
    """The design, for the run manifest."""
    return {
        "design_id": design.design_id,
        "cell_line": design.cell_line,
        "rrid": design.rrid,
        "plate_format": design.plate_format,
        "combinations": design.combinations,
        "replicates": design.replicates,
        "edge_policy": design.edge_policy,
        "synergy_model": design.analysis.synergy_model if design.analysis else None,
        "committed_at": (
            design.analysis.committed_at.isoformat() if design.analysis else None
        ),
    }
