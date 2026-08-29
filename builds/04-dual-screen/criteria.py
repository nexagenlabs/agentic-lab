"""Criteria are versioned data, and a run refuses to start without them.

The chapter argues that the hard part of automated screening is not the agent
but writing down criteria you believed you already had. This module is the
consequence of taking that seriously: the criteria are a file, the file is
validated, and a file that does not validate stops the run.

There is deliberately no default. A screening run that silently fell back to
built-in criteria would produce verdicts nobody could reconstruct, which is
worse than a run that does not start.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CriteriaError(RuntimeError):
    """The criteria file is missing, unreadable, or does not validate.

    Raised rather than returned. Rule 4 asks for a structured object on error
    paths that feed a model, and this one does not: it halts the process
    before any model sees anything, and a caller that ignored a returned error
    here would screen under criteria it never loaded.
    """


class Criterion(BaseModel):
    """One rule, carrying the identifier a verdict cites."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Criteria(BaseModel):
    """A whole criteria file.

    ``extra="forbid"`` is the point of the model rather than a detail. A
    misspelled key in a criteria file would otherwise be accepted and ignored,
    and the run would screen against a rule the author believed they had
    written.
    """

    model_config = ConfigDict(extra="forbid")

    version: int
    question: str = Field(min_length=1)
    include_if_all: list[Criterion] = Field(min_length=1)
    exclude_if_any: list[Criterion] = Field(default_factory=list)
    # The book admits one answer to ambiguity. Anything else in this field is
    # a criteria file this build declines to run.
    on_ambiguity: Literal["flag"]

    def criterion_ids(self) -> list[str]:
        """Every identifier a verdict is allowed to cite."""
        return [c.id for c in self.include_if_all] + [c.id for c in self.exclude_if_any]


def load_criteria(path: str | Path) -> Criteria:
    """Read and validate a criteria file, or raise ``CriteriaError``."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CriteriaError(f"criteria file could not be read: {path}: {error}") from error

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise CriteriaError(f"criteria file is not valid YAML: {path}: {error}") from error

    if not isinstance(parsed, dict):
        raise CriteriaError(f"criteria file is not a mapping: {path}")

    try:
        return Criteria(**parsed)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        raise CriteriaError(f"criteria file failed validation: {path}: {problems}") from error
