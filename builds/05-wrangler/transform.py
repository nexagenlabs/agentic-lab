"""Stage three: the transformation, with no model in sight.

Everything below this line is deterministic. The agent proposed a mapping and
a human signed it; from here on the work is done by code that will produce the
same bytes tomorrow. That division is the whole build: the agent supplies
judgement about what a column means, and code supplies every transformation,
conversion and total.

``apply_mapping`` is printed in the chapter and does the two steps a mapping
describes: rename, and melt if the layout is wide. The steps after it, in
``tidy``, are the ones a real export needs and the page has no room for:
lifting the plate identifier out of a merged title cell, normalising well
names, converting units, and putting the columns in a fixed order so that two
runs are byte-identical.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from models import FileMapping

# What a wide export keeps when the well columns are melted away. A wide
# instrument file names its wells in the header, so everything that is not a
# well is an identifier.
ID_COLS = ["measure"]

# The order every tidy table comes out in. Fixed, and sorted on afterwards,
# because determinism is what makes Chapter 9 possible and a set iteration
# somewhere upstream is what quietly takes it away.
TIDY_COLUMNS = ["plate_id", "well", "compound", "conc_nM", "viability", "replicate"]

WELL_RE = re.compile(r"^([A-Ha-h])\s*0*(\d{1,2})$")

# Multiplier into nanomolar. The agent reports which unit it believes it saw;
# this table converts. A model asked to do the conversion would sometimes be
# right.
TO_NM = {"nM": 1.0, "uM": 1000.0, "µM": 1000.0, "mM": 1_000_000.0, "M": 1e9}


class TransformError(RuntimeError):
    """The file cannot be transformed under this mapping."""


def apply_mapping(path: Path, mapping: FileMapping) -> pd.DataFrame:
    if mapping.approved_at is None:
        raise RuntimeError("Unapproved mapping; refusing to transform.")

    df = pd.read_csv(path, header=mapping.header_row, dtype=str,
                     keep_default_na=False)
    df = df.rename(columns={c.source_column: c.target_column
                            for c in mapping.columns})
    if mapping.layout == "wide":
        df = df.melt(id_vars=ID_COLS, var_name="well", value_name="value")
    return df


def normalise_well(value: str) -> str:
    """A01 form, from whatever the instrument wrote.

    Instruments disagree about zero padding and whitespace, and a well that
    does not match the plate map is assertion five waiting to happen. The
    normalisation is deliberately narrow: anything that is not recognisably a
    well is returned unchanged so that the assertion catches it rather than
    this function silently inventing a well that parses.
    """
    text = str(value).strip()
    match = WELL_RE.match(text)
    if not match:
        return text
    row, column = match.groups()
    return f"{row.upper()}{int(column):02d}"


def plate_id_from_preamble(path: Path, header_row: int) -> str | None:
    """Lift a plate identifier out of the lines above the header.

    A merged title cell is where instruments put the one identifier that
    matters and where every naive reader loses it.
    """
    lines = path.read_text(errors="replace").splitlines()[:header_row]
    for line in lines:
        found = re.search(r"\bP\d{3}\b", line)
        if found:
            return found.group(0)
    return None


def _pivot_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Turn the melted wide export into one row per well.

    A wide plate export names its wells across the header and stacks the
    measured variables down the first column, so after the melt every fact
    about a well is a row and the well needs its facts gathered back up.
    """
    table = df.pivot(index="well", columns="measure", values="value")
    table.columns.name = None
    return table.reset_index()


def _to_nanomolar(values: pd.Series, unit: str | None) -> pd.Series:
    if unit is None:
        raise TransformError("concentration column has no declared unit")
    if unit not in TO_NM:
        raise TransformError(f"unknown concentration unit {unit!r}")
    return pd.to_numeric(values, errors="coerce") * TO_NM[unit]


def concentration_unit(mapping: FileMapping) -> str | None:
    """The unit the approved mapping records for the concentration column."""
    for column in mapping.columns:
        if column.target_column.startswith("conc"):
            return column.detected_unit
    return None


def tidy(path: Path, mapping: FileMapping) -> pd.DataFrame:
    """The whole deterministic path, from export to tidy table."""
    frame = apply_mapping(path, mapping)

    if mapping.layout == "wide":
        frame = _pivot_wide(frame)

    if "well" not in frame.columns:
        raise TransformError("mapping produced no well column")
    frame["well"] = frame["well"].map(normalise_well)

    if "plate_id" not in frame.columns:
        plate_id = plate_id_from_preamble(path, mapping.header_row)
        if plate_id is None:
            raise TransformError("no plate identifier in the file or the mapping")
        frame["plate_id"] = plate_id

    unit = concentration_unit(mapping)
    source = "conc_nM" if "conc_nM" in frame.columns else "conc"
    if source not in frame.columns:
        raise TransformError("mapping produced no concentration column")
    frame["conc_nM"] = _to_nanomolar(frame[source], unit)
    if source != "conc_nM":
        frame = frame.drop(columns=[source])

    for column in ("viability", "replicate"):
        if column not in frame.columns:
            raise TransformError(f"mapping produced no {column} column")
    frame["viability"] = pd.to_numeric(frame["viability"], errors="coerce")
    frame["replicate"] = pd.to_numeric(frame["replicate"], errors="coerce")

    missing = [c for c in TIDY_COLUMNS if c not in frame.columns]
    if missing:
        raise TransformError(f"tidy table is missing columns: {missing}")

    extra = [c for c in frame.columns if c not in TIDY_COLUMNS]
    frame = frame[TIDY_COLUMNS + extra]
    return frame.sort_values(["plate_id", "well"]).reset_index(drop=True)


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialise deterministically, for the byte-identical assertion."""
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def summarise(frame: pd.DataFrame) -> dict[str, Any]:
    """Counts, taken in Python. The agent is never asked how many rows."""
    return {
        "rows": len(frame),
        "wells": int(frame["well"].nunique()),
        "plates": int(frame["plate_id"].nunique()),
        "columns": list(frame.columns),
    }
