"""Stage four: a schema that knows about units.

The bounds encode what is physically possible, not what is tidy. Viability
starts at minus 0.2 because a treated well legitimately reads below blank, and
a schema that forbids real data is a broken schema: it will be switched off by
the first person it inconveniences, and then nothing is checked at all.

strict rejects a column nobody declared, which is how a field added by a
software update becomes an error rather than a surprise. coerce does the type
conversion in one declared place, after everything has been read as text.
"""

import pandera.pandas as pa
from pandera.typing import Series


class TidyReadings(pa.DataFrameModel):
    plate_id:    Series[str]   = pa.Field(str_matches=r"^P\d{3}$")
    well:        Series[str]   = pa.Field(str_matches=r"^[A-H](0[1-9]|1[0-2])$")
    compound:    Series[str]   = pa.Field(
        nullable=False,
        str_matches=r"^(?![0-9]{1,2}-[A-Za-z]{3}$).+",   # not a date
    )
    conc_nM:     Series[float] = pa.Field(ge=0, le=1e7)
    viability:   Series[float] = pa.Field(ge=-0.2, le=1.5)
    replicate:   Series[int]   = pa.Field(ge=1, le=6)

    class Config:
        strict = True          # an unexpected column is an error
        coerce = True
