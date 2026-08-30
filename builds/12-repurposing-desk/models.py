"""What moves between the stages of the desk.

Every one of these is a record rather than a bag of arguments, because the
manifest has to be able to say what each stage received and produced. A stage
that took a dictionary and returned a dictionary would be a stage whose
provenance could only be reconstructed by reading its code.

``Question`` carries the compound-to-ligand map, and that field is the least
elegant thing in the file. It is here because a desk that goes from literature
to docking has to connect a compound named in an abstract to a structure a
docking engine can read, and in a real system that connection comes from a
chemical registry with its own identifiers and its own errors. Putting it in
the question makes it a declared input with a hash in the manifest rather than
a lookup somebody did in their head.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    text: str = Field(min_length=1)
    target: str
    target_line: str
    shortlist_n: int = Field(ge=1, le=50)
    criteria_version: int
    # Compound name to the ligand identifier a docking run can address. A
    # declared input, hashed into the manifest, rather than a mapping somebody
    # held in their head between two stages.
    compound_ligands: dict[str, str]

    @classmethod
    def load(cls, path: str | Path) -> Question:
        body = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(**body)


class Verdict(BaseModel):
    """Build 03's shape, copied. ``criteria_version`` on every one."""

    model_config = ConfigDict(extra="forbid")

    pmid: str
    decision: Literal["include", "exclude", "flag"]
    reason: str
    criteria_version: int
    compounds: list[str] = Field(default_factory=list)


class Screened(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict]
    criteria_version: int

    @property
    def included(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.decision == "include"]

    @property
    def flagged(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.decision == "flag"]

    @property
    def excluded(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.decision == "exclude"]

    def compounds(self) -> list[str]:
        """Every compound named in a record that survived screening."""
        out: set[str] = set()
        for verdict in self.included:
            out.update(verdict.compounds)
        return sorted(out)


class Resolved(BaseModel):
    """What the triage agent decided about the records screening flagged."""

    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict]
    steps_taken: dict[str, int] = Field(default_factory=dict)

    def compounds(self) -> list[str]:
        out: set[str] = set()
        for verdict in self.verdicts:
            if verdict.decision == "include":
                out.update(verdict.compounds)
        return sorted(out)


class StructureRecord(BaseModel):
    """Build 08's shape, copied, with the two fields that carry the weight."""

    model_config = ConfigDict(extra="forbid")

    target: str
    source: Literal["EXPERIMENTAL", "PREDICTED"]
    identifier: str
    method: str | None
    resolution_angstrom: float | None
    ligand_state: str
    cocrystal_ligand: str | None
    prediction_confidence: float | None
    retrieved_at: datetime


class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[StructureRecord]
    ligands: dict[str, str]

    @property
    def sources(self) -> set[str]:
        return {record.source for record in self.records}


class Pose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    score: float


class DockingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compound: str
    ligand_id: str
    target: str
    poses: list[Pose] = Field(min_length=1)
    source: Literal["EXPERIMENTAL", "PREDICTED"]
    engine: str
    seed: int
    exhaustiveness: int
    # Which records put this compound in front of the docking stage. Carried
    # here because `rank` takes only the results, so the evidence has to
    # travel with them rather than be joined back on afterwards.
    evidence_pmids: list[str] = Field(default_factory=list)

    @property
    def top_score(self) -> float:
        """The number a ranking uses, and the only one it should use."""
        return min(pose.score for pose in self.poses)

    @property
    def cluster(self) -> int:
        """Poses within half a kcal of the best. Kept because the whole
        distribution is the evidence, as Build 08 argues at length."""
        best = self.top_score
        return sum(1 for pose in self.poses if pose.score <= best + 0.5)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int
    compound: str
    ligand_id: str
    target: str
    score: float
    cluster: int
    source: str
    evidence_pmids: list[str] = Field(default_factory=list)


class Ranked(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[Candidate]
    homogeneous: bool

    def head(self, count: int) -> list[Candidate]:
        return self.candidates[:count]


class Shortlist(BaseModel):
    """What the desk returns. It is not an answer and does not claim to be."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[Candidate]
    protocol: dict[str, Any]
    manifest: dict[str, Any]

    def compounds(self) -> list[str]:
        return [candidate.compound for candidate in self.candidates]
