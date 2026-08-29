"""A docking score is a ranking, not a measurement.

Score to affinity correlations run from 0.10 to 0.38 across seven programs on
roughly 1,300 complexes, and one benchmark recorded AutoDock Vina at minus
0.18. Enrichment is the claim docking supports: given a library, it puts more
actives near the top than chance would. Nothing in this build may present a
score as an affinity, and ``affinity.py`` refuses to, loudly.

Everything in this file exists to make the parts of a docking run that
normally live in somebody's memory into fields that a manifest can carry: what
the structure was and where it came from, where the box was and why, what was
done to the receptor before the run, and which seed produced the numbers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StructureRecord(BaseModel):
    target: str
    source: Literal["EXPERIMENTAL", "PREDICTED"]
    identifier: str                  # PDB ID, or model accession
    method: str | None               # X-ray, cryo-EM, AF3, HelixFold3
    resolution_angstrom: float | None
    ligand_state: Literal["holo", "apo", "predicted_holo", "unknown"]
    cocrystal_ligand: str | None
    prediction_confidence: float | None      # mean pLDDT over the pocket
    retrieved_at: datetime

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def provenance_is_consistent(self) -> StructureRecord:
        """The two fields that carry the weight have to mean something.

        ``prediction_confidence`` is specified over the pocket rather than the
        whole chain, because a model with excellent global confidence and a
        poorly resolved binding site is exactly the case that misleads you. A
        predicted structure that does not carry one is not usable evidence,
        and an experimental structure that does carry one is reporting a
        number about something that was measured.
        """
        if self.source == "PREDICTED" and self.prediction_confidence is None:
            raise ValueError(
                f"{self.identifier}: a predicted structure must carry "
                "prediction_confidence, the mean pLDDT over the pocket. "
                "Global confidence is not the number that matters here."
            )
        if self.source == "EXPERIMENTAL" and self.prediction_confidence is not None:
            raise ValueError(
                f"{self.identifier}: an experimental structure has no pLDDT. "
                "Recording one implies a model where there is a measurement."
            )
        if self.ligand_state == "holo" and not self.cocrystal_ligand:
            raise ValueError(
                f"{self.identifier}: holo means a ligand is present, so name "
                "it. A holo structure with no named ligand is a claim nobody "
                "can check."
            )
        return self


class DockingBox(BaseModel):
    strategy: Literal["cocrystal_ligand", "residue_list", "explicit"]
    centre_xyz: tuple[float, float, float]
    size_xyz: tuple[float, float, float]
    defining_residues: list[str] | None
    justification: str

    # Enforced at construction: within a comparison set, every target
    # must use the same strategy. Mixed strategies are not comparable.
    comparison_set_id: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def the_strategy_is_supported_by_what_it_names(self) -> DockingBox:
        if self.strategy == "residue_list" and not self.defining_residues:
            raise ValueError(
                "a residue_list box must list the residues that define it"
            )
        if len(self.justification.split()) < 5:
            raise ValueError(
                "a box needs a written justification. Where the box went is "
                "the decision that most often makes two runs incomparable, "
                "and it is almost never recorded."
            )
        return self


class PreparationDecisions(BaseModel):
    """Every preparation decision, declared. Not one of them has a default.

    Undeclared defaults are how two runs of the same nominal protocol diverge.
    Somebody kept the waters, somebody else stripped them, both wrote down
    "prepared in the usual way", and the numbers stopped being comparable
    without anybody making a mistake.
    """

    model_config = ConfigDict(extra="forbid")

    assay_ph: float = Field(gt=0, lt=14)
    protonation_state: str = Field(min_length=1)
    crystallographic_waters: Literal["retained", "removed", "selected"]
    waters_retained: list[str] | None = None
    metals_and_cofactors: str = Field(min_length=1)
    ligand_tautomer: str = Field(min_length=1)

    @model_validator(mode="after")
    def selected_waters_are_named(self) -> PreparationDecisions:
        if self.crystallographic_waters == "selected" and not self.waters_retained:
            raise ValueError(
                "waters were kept selectively, so say which ones. A selection "
                "nobody recorded is not a protocol."
            )
        return self


class Pose(BaseModel):
    """One pose out of the search, with its coordinates kept.

    The coordinates are here because the whole distribution is the evidence. A
    top score from a single outlier pose is different evidence from one
    supported by a tight cluster, and the cluster is only visible if you keep
    the poses rather than the best number.
    """

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    score: float
    coordinates: list[tuple[float, float, float]]


class DockingResult(BaseModel):
    """One ligand against one receptor, with the run recorded beside it."""

    model_config = ConfigDict(extra="forbid")

    ligand_id: str
    target: str
    poses: list[Pose] = Field(min_length=1)
    seed: int
    exhaustiveness: int = Field(ge=1)
    engine: str

    @property
    def top(self) -> Pose:
        return min(self.poses, key=lambda pose: (pose.score, pose.rank))

    @property
    def top_score(self) -> float:
        """The number a ranking uses, and the only one it should use."""
        return self.top.score
