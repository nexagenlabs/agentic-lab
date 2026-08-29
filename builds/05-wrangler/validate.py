"""Running the schema, and reading the bounds back out of it.

Everything here derives from ``schema.TidyReadings``. Nothing restates a
bound. That matters because assertion 4 is "range plausibility per column,
from the schema", and a second copy of the numbers would drift from the first
the day somebody widened one of them, leaving an assertion that checks a range
the schema no longer declares.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pandera.errors
from schema import TidyReadings


@dataclass(frozen=True)
class Bound:
    """One column's constraint, read out of the pandera schema."""

    dtype: str
    ge: float | None = None
    le: float | None = None
    str_matches: str | None = None
    nullable: bool = False

    @property
    def numeric(self) -> bool:
        return self.dtype.startswith(("int", "float"))


class SchemaError(RuntimeError):
    """The tidy table does not satisfy the schema."""

    def __init__(self, failures: list[str]) -> None:
        super().__init__("; ".join(failures) or "schema validation failed")
        self.failures = failures


def _bounds() -> dict[str, Bound]:
    schema = TidyReadings.to_schema()
    out: dict[str, Bound] = {}
    for name, column in schema.columns.items():
        ge = le = None
        pattern = None
        for check in column.checks:
            stats = getattr(check, "statistics", None) or {}
            if check.name == "greater_than_or_equal_to":
                ge = stats.get("min_value")
            elif check.name == "less_than_or_equal_to":
                le = stats.get("max_value")
            elif check.name == "str_matches":
                pattern = stats.get("pattern")
        out[name] = Bound(
            dtype=str(column.dtype),
            ge=ge,
            le=le,
            str_matches=pattern,
            nullable=bool(column.nullable),
        )
    return out


# Read once at import. The schema is a declaration, not a moving target.
BOUNDS: dict[str, Bound] = _bounds()
STRICT: bool = bool(TidyReadings.to_schema().strict)
COERCE: bool = bool(TidyReadings.to_schema().coerce)


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate under the printed schema, or raise listing every failure.

    ``lazy=True`` so that a person fixing an export gets the whole list rather
    than one round trip per column.
    """
    try:
        return TidyReadings.validate(frame, lazy=True)
    except pandera.errors.SchemaErrors as errors:
        failures = []
        for _, row in errors.failure_cases.iterrows():
            failures.append(
                f"{row.get('column')}: {row.get('check')} failed for "
                f"{row.get('failure_case')!r}"
            )
        raise SchemaError(sorted(set(failures))) from errors
    except pandera.errors.SchemaError as error:
        raise SchemaError([str(error)]) from error


def schema_as_dict() -> dict[str, Any]:
    """The declared bounds, for the run manifest."""
    return {
        name: {
            "dtype": bound.dtype,
            "ge": bound.ge,
            "le": bound.le,
            "str_matches": bound.str_matches,
            "nullable": bound.nullable,
        }
        for name, bound in BOUNDS.items()
    }
