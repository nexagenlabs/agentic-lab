"""Stage two: the mapping is a proposal, and it is data.

A proposal, because the agent suggests it and a human signs it. Data, because
it is written to a file, versioned, and replayed thereafter with no model call
at all. The second run of an instrument export costs nothing and cannot drift.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ColumnMapping(BaseModel):
    source_column: str
    target_column: str
    detected_unit: str | None      # what the agent believes it found
    unit_evidence: str             # where in the file it saw that
    confidence: Literal["high", "low"]

class FileMapping(BaseModel):
    instrument: str
    layout: Literal["wide", "long"]
    header_row: int
    columns: list[ColumnMapping]
    approved_by: str | None = None       # blank until a human signs it
    approved_at: datetime | None = None
