"""The whole path from export to tidy table, with the six assertions in order.

The order is not arbitrary. Cheap structural checks run before expensive ones,
and every check runs before the schema so that a failure names the property
that broke rather than the type conversion that noticed. Identifier integrity
runs after the schema on purpose: a transposed plate passes the schema
completely, and the point of the chapter's failure account is that it takes
assertion five to catch it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from assertions import (
    AssertionFailed,
    Expectation,
    UnitDeclarationFailed,
    assert_deterministic,
    assert_identifier_integrity,
    assert_no_silent_nulls,
    assert_ranges_plausible,
    assert_row_conservation,
    assert_units_declared,
)
from models import FileMapping
from transform import (
    apply_mapping,
    concentration_unit,
    normalise_well,
    tidy,
    to_csv_bytes,
)
from validate import SchemaError, validate

# The plate this build's fixtures were run on. Build 06 generates these from a
# design file; here it is declared, because a plate map you cannot state is a
# plate map you cannot check against.
PLATE_MAP = {"A01", "A02", "A03", "B01", "B02", "B03"}


class UnitCollision(RuntimeError):
    """Two frames carry the same quantity in different units."""


def load_mapping(path: str | Path) -> FileMapping:
    """Read an approved mapping. No model call, ever, on this path."""
    body = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return FileMapping(**body)


def quantity_of(column: str) -> tuple[str, str | None]:
    """Split a column name into its quantity and its unit suffix."""
    if "_" not in column:
        return column, None
    stem, suffix = column.rsplit("_", 1)
    if suffix and not suffix.islower():
        return stem, suffix
    return column, None


def merge_tidy(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """Merge two tidy tables, refusing a unit collision.

    Two columns naming the same quantity in different units must collide by
    name rather than concatenate. Concatenating them is how a micromolar
    column ends up stacked under a nanomolar one and every number in the
    result is wrong by a thousand, with nothing anywhere to say so.
    """
    left_units = {quantity_of(c): c for c in left.columns}
    right_units = {quantity_of(c): c for c in right.columns}

    collisions = []
    for (quantity, unit), column in left_units.items():
        for (other_quantity, other_unit), other_column in right_units.items():
            if quantity == other_quantity and unit != other_unit:
                collisions.append((column, other_column))
    if collisions:
        raise UnitCollision(
            "the same quantity appears in different units: "
            + ", ".join(f"{a} against {b}" for a, b in sorted(collisions))
            + ". Convert to one unit before merging; concatenating these "
            "would be a silent thousandfold error."
        )
    return pd.concat([left, right], ignore_index=True)


def tidy_preserving_units(path: str | Path, mapping: FileMapping) -> pd.DataFrame:
    """Shape a file without normalising its concentration unit.

    This is what a careless pipeline does: it renames and reshapes, and leaves
    the concentration in whatever unit the instrument wrote, carrying the unit
    in the column name as the convention requires. Two such frames from two
    instruments are exactly the pair that must refuse to merge.
    """
    frame = apply_mapping(Path(path), mapping)
    unit = concentration_unit(mapping)
    if unit is None:
        raise UnitCollision(f"{Path(path).name} declares no concentration unit")
    frame = frame.rename(columns={"conc": f"conc_{unit}"})
    frame["well"] = frame["well"].map(normalise_well)
    return frame


def run(
    path: str | Path,
    mapping: FileMapping,
    expected: Expectation,
    *,
    plate_map: set[str] | None = None,
) -> dict[str, Any]:
    """Transform and check one export, raising the first assertion that fails."""
    path = Path(path)
    plate_map = PLATE_MAP if plate_map is None else plate_map

    # Read the baseline exactly as apply_mapping does, or the null count
    # this compares against is a count of a file nobody transformed.
    raw = pd.read_csv(path, header=mapping.header_row, dtype=str,
                      keep_default_na=False)
    frame = tidy(path, mapping)

    assert_row_conservation(frame, expected)
    assert_no_silent_nulls(raw, frame, expected)
    assert_units_declared(frame)
    assert_ranges_plausible(frame)

    checked = validate(frame)

    assert_identifier_integrity(checked, plate_map)

    first = to_csv_bytes(checked)
    second = to_csv_bytes(validate(tidy(path, mapping)))
    assert_deterministic(first, second)

    return {
        "file": path.name,
        "rows": len(checked),
        "wells": int(checked["well"].nunique()),
        "bytes": len(first),
        "frame": checked,
    }


def mapping_for(path: str | Path) -> FileMapping:
    """The approved mapping for a fixture, by name.

    A fixture with its own mapping uses it; everything else in the long shape
    shares the one the qPCR export was signed off with.
    """
    path = Path(path)
    here = Path(__file__).resolve().parent / "mappings"
    named = here / f"{path.stem}.yaml"
    return load_mapping(named if named.exists() else here / "qpcr_long.yaml")


def check_expected(path: str | Path, mapping: FileMapping) -> dict[str, Any]:
    """Run a broken fixture and report which assertion fired.

    Returns rather than raises, because the test that drives the seven broken
    fixtures wants to compare what fired against what the .expected.json says
    should have fired, and an exception per fixture would stop at the first.
    """
    path = Path(path)
    expectation_file = path.with_suffix("").with_suffix(".expected.json")
    declared = json.loads(expectation_file.read_text(encoding="utf-8"))
    expected = Expectation(wells=declared["expected_wells"])

    if declared.get("fires_on") == "merge":
        partner = path.with_name(declared["merge_with"])
        try:
            merge_tidy(
                tidy_preserving_units(path, mapping_for(path)),
                tidy_preserving_units(partner, mapping_for(partner)),
            )
        except UnitCollision as failure:
            return {"fired": 3, "declared": declared["expected_assertion"],
                    "detail": str(failure), "fixture": path.name}
        return {"fired": None, "declared": declared["expected_assertion"],
                "detail": "the merge did not collide", "fixture": path.name}

    try:
        run(path, mapping, expected)
    except AssertionFailed as failure:
        return {"fired": failure.number, "declared": declared["expected_assertion"],
                "detail": failure.detail, "fixture": path.name}
    except SchemaError as failure:
        # The schema caught something the numbered assertions did not. That is
        # reportable rather than silently equivalent to one of the six.
        return {"fired": "schema", "declared": declared["expected_assertion"],
                "detail": "; ".join(failure.failures), "fixture": path.name}
    return {"fired": None, "declared": declared["expected_assertion"],
            "detail": "nothing fired: this fixture passed", "fixture": path.name}


__all__ = [
    "PLATE_MAP",
    "Expectation",
    "UnitCollision",
    "UnitDeclarationFailed",
    "apply_mapping",
    "check_expected",
    "load_mapping",
    "mapping_for",
    "merge_tidy",
    "run",
    "tidy_preserving_units",
]
