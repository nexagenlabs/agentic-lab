"""The six assertions from Table 5.2.

Each raises a named exception carrying which assertion failed, because "the
pipeline threw" is not a diagnosis and the whole point of numbering them is
that a person reading a failure knows immediately which property broke.

Assertion five is the cheapest one on the list and the one the chapter's
failure account turns on. A transposed plate passes every schema check ever
written: the values are in range, the types are right, the file is beautiful.
It fails identifier integrity in about one second, and nobody ran it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from validate import BOUNDS


class AssertionFailed(RuntimeError):
    """Base for the six. Carries the assertion number and name."""

    number = 0
    name = "unknown"

    def __init__(self, detail: str, **context: Any) -> None:
        super().__init__(f"assertion {self.number} ({self.name}): {detail}")
        self.detail = detail
        self.context = context

    def as_dict(self) -> dict[str, Any]:
        return {
            "assertion": self.number,
            "name": self.name,
            "detail": self.detail,
            **self.context,
        }


class RowConservationFailed(AssertionFailed):
    number, name = 1, "row_conservation"


class SilentNullsFailed(AssertionFailed):
    number, name = 2, "no_silent_nulls"


class UnitDeclarationFailed(AssertionFailed):
    number, name = 3, "unit_declared"


class RangePlausibilityFailed(AssertionFailed):
    number, name = 4, "range_plausibility"


class IdentifierIntegrityFailed(AssertionFailed):
    number, name = 5, "identifier_integrity"


class DeterminismFailed(AssertionFailed):
    number, name = 6, "determinism"


ASSERTIONS = {
    1: RowConservationFailed,
    2: SilentNullsFailed,
    3: UnitDeclarationFailed,
    4: RangePlausibilityFailed,
    5: IdentifierIntegrityFailed,
    6: DeterminismFailed,
}


@dataclass
class Removal:
    """A row that left the table, and why it was allowed to."""

    pmid_or_well: str
    reason: str


@dataclass
class Expectation:
    """What the caller declared before the transformation ran."""

    wells: int
    targets: int = 1
    declared_removals: list[Removal] = field(default_factory=list)
    declared_new_nulls: int = 0

    @property
    def expected_rows(self) -> int:
        return self.wells * self.targets - len(self.declared_removals)


def assert_row_conservation(frame: pd.DataFrame, expected: Expectation) -> None:
    """Wells in equals rows out, allowing for declared melts and removals.

    Rows may be removed with a logged reason. Rows may never simply be absent,
    which is the failure this catches: a filter somewhere upstream that
    dropped what it could not parse and said nothing.
    """
    actual = len(frame)
    if actual != expected.expected_rows:
        raise RowConservationFailed(
            f"expected {expected.expected_rows} rows "
            f"({expected.wells} wells times {expected.targets} targets, "
            f"less {len(expected.declared_removals)} declared removals), "
            f"got {actual}",
            expected_rows=expected.expected_rows,
            actual_rows=actual,
            removals=[r.__dict__ for r in expected.declared_removals],
        )


def assert_no_silent_nulls(
    before: pd.DataFrame, after: pd.DataFrame, expected: Expectation
) -> None:
    """Count nulls on both sides and require the delta to be declared.

    A transformation that turns a value into a null has lost data. It is
    allowed to, if somebody said it would.
    """
    nulls_before = int(before.isna().sum().sum())
    nulls_after = int(after.isna().sum().sum())
    delta = nulls_after - nulls_before
    if delta != expected.declared_new_nulls:
        raise SilentNullsFailed(
            f"nulls went from {nulls_before} to {nulls_after}, a change of "
            f"{delta}, and {expected.declared_new_nulls} were declared",
            nulls_before=nulls_before,
            nulls_after=nulls_after,
            delta=delta,
            declared=expected.declared_new_nulls,
        )


# Columns that carry no unit because the quantity has none. Named rather
# than guessed at, so that adding a column forces a decision instead of
# inheriting silence.
DIMENSIONLESS = {"viability", "replicate"}
IDENTIFIERS = {"plate_id", "well", "compound"}


def assert_units_declared(frame: pd.DataFrame) -> None:
    """Every measured column carries its unit in its name.

    ``conc_nM``, never ``conc``. The check is on the name rather than the
    dtype, because a column read as text is still a measurement and a unit
    that only appears once the value is parsed is a unit nobody declared.
    """
    offenders = []
    for name in frame.columns:
        if name in DIMENSIONLESS or name in IDENTIFIERS:
            continue
        suffix = name.rsplit("_", 1)[-1] if "_" in name else ""
        if not suffix or suffix.islower():
            offenders.append(name)
    if offenders:
        raise UnitDeclarationFailed(
            f"numeric columns with no unit in the name: {sorted(offenders)}",
            columns=sorted(offenders),
        )


def assert_ranges_plausible(frame: pd.DataFrame) -> None:
    """Every value inside the bounds the schema declares."""
    offenders: dict[str, Any] = {}
    for name, bound in BOUNDS.items():
        if name not in frame.columns or not bound.numeric:
            continue
        column = pd.to_numeric(frame[name], errors="coerce").dropna()
        if bound.ge is not None and bool((column < bound.ge).any()):
            offenders[name] = f"below {bound.ge}"
        if bound.le is not None and bool((column > bound.le).any()):
            offenders[name] = f"above {bound.le}"
    if offenders:
        raise RangePlausibilityFailed(
            f"values outside declared bounds: {offenders}", columns=offenders
        )


def assert_identifier_integrity(frame: pd.DataFrame, plate_map: set[str]) -> None:
    """Every well in the table exists on the plate map.

    One second of work. It is the assertion that catches a transposed plate,
    a shifted label block and a well the instrument invented, and it is the
    one nobody runs because the file looks fine.
    """
    seen = set(frame["well"].astype(str))
    unknown = sorted(seen - plate_map)
    absent = sorted(plate_map - seen)
    if unknown or absent:
        raise IdentifierIntegrityFailed(
            f"{len(unknown)} wells not on the plate map "
            f"(first: {unknown[:3]}), {len(absent)} plate map wells missing "
            f"(first: {absent[:3]})",
            unknown_wells=unknown,
            missing_wells=absent,
        )


def assert_deterministic(first: bytes, second: bytes) -> None:
    """The same input twice, byte for byte.

    Non-determinism here means something iterated a set or read a clock, and
    it makes the run manifest of Chapter 9 impossible: a hash that changes
    when nothing changed proves nothing about anything.
    """
    if first != second:
        raise DeterminismFailed(
            f"two runs produced different output: {len(first)} bytes then "
            f"{len(second)} bytes",
            first_bytes=len(first),
            second_bytes=len(second),
        )
