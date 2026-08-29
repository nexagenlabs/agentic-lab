"""The verdict a screening run produces, one per record.

Two fields carry more weight than their size suggests. ``criteria_failed``
names which rule caused an exclusion, so that forty exclusions citing one
criterion read as a diagnosis rather than a mystery. ``criteria_version`` is
stamped on every verdict, so a run screened under version 2 can never be
silently compared with one screened under version 3.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Verdict(BaseModel):
    pmid: str
    decision: Literal["include", "exclude", "flag"]
    criteria_met: list[str] = Field(default_factory=list)
    criteria_failed: list[str] = Field(default_factory=list)
    reason: str = Field(max_length=300)
    confidence: Literal["high", "low"]
    criteria_version: int
