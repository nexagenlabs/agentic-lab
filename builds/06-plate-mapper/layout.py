"""Where every well goes, reproducibly.

Two properties matter more than the arrangement itself.

Controls sit on every plate rather than on a reference plate, because plate
effects are real and a control measured on Tuesday cannot normalise a
treatment measured on Thursday.

The randomisation is seeded and the seed lives in the design. A layout you
cannot reproduce is a layout nothing can check: the wrangler from Build 05 has
to be able to regenerate this exact map to verify returning data against it,
and it cannot do that from a shuffle nobody recorded.

A note on capacity. The printed design asks for more wells than its own plate
has, so the layout spans plates. See HANDOFF.md for the arithmetic.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import product
from typing import Any

from design import Design

ROW_LETTERS = "ABCDEFGHIJKLMNOP"


@dataclass(frozen=True)
class Assignment:
    """One well and what is in it."""

    plate: int
    well: str
    role: str
    drug_a_uM: float | None = None
    drug_b_uM: float | None = None
    replicate: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "plate": self.plate, "well": self.well, "role": self.role,
            "drug_a_uM": self.drug_a_uM, "drug_b_uM": self.drug_b_uM,
            "replicate": self.replicate,
        }


@dataclass
class Layout:
    """Every plate the design needs, and the seed that produced them."""

    assignments: tuple[Assignment, ...] = field(default_factory=tuple)
    seed: int = 0
    plate_format: int = 96
    plates: int = 1

    def for_plate(self, plate: int) -> list[Assignment]:
        return [a for a in self.assignments if a.plate == plate]

    def counts(self, plate: int) -> dict[str, int]:
        """Well counts by role for one plate. They must sum to the format."""
        wells = self.for_plate(plate)
        tally: dict[str, int] = {}
        for assignment in wells:
            tally[assignment.role] = tally.get(assignment.role, 0) + 1
        tally["total"] = len(wells)
        return tally

    def well_map(self) -> dict[tuple[int, str], Assignment]:
        return {(a.plate, a.well): a for a in self.assignments}


def all_wells(rows: int, columns: int) -> list[str]:
    return [f"{ROW_LETTERS[r]}{c + 1:02d}"
            for r in range(rows) for c in range(columns)]


def perimeter_wells(rows: int, columns: int) -> set[str]:
    out = set()
    for r in range(rows):
        for c in range(columns):
            if r in (0, rows - 1) or c in (0, columns - 1):
                out.add(f"{ROW_LETTERS[r]}{c + 1:02d}")
    return out


def build_layout(design: Design) -> Layout:
    """Lay the design out across as many plates as it needs."""
    rows, columns = design.rows, design.columns
    every = all_wells(rows, columns)
    perimeter = perimeter_wells(rows, columns)

    if design.edge_policy == "exclude_perimeter":
        usable = [w for w in every if w not in perimeter]
    else:
        usable = list(every)

    controls_needed = design.controls.total
    per_plate = len(usable) - controls_needed
    if per_plate <= 0:
        raise ValueError(
            f"controls alone need {controls_needed} of {len(usable)} usable "
            "wells; there is no room for treatment"
        )

    treatments = []
    axis_a, axis_b = (design.axes[key] for key in sorted(design.axes))
    for replicate in range(1, design.replicates + 1):
        for a, b in product(axis_a.series_uM(), axis_b.series_uM()):
            treatments.append((a, b, replicate))

    plates = math.ceil(len(treatments) / per_plate)
    assignments: list[Assignment] = []
    cursor = 0

    for plate in range(1, plates + 1):
        # Controls first and always, on this plate, not a reference plate.
        slots = list(usable)
        if design.randomise_within_plate:
            # A fresh Random per plate, derived from the recorded seed, so the
            # layout is reproducible plate by plate rather than dependent on
            # how many plates happened to come before it.
            random.Random(design.randomisation_seed + plate).shuffle(slots)

        control_roles = (
            ["vehicle"] * design.controls.vehicle.wells
            + ["untreated"] * design.controls.untreated.wells
            + ["blank"] * design.controls.blank.wells
        )
        for role, well in zip(control_roles, slots[:controls_needed], strict=True):
            assignments.append(Assignment(plate, well, role))

        for well in slots[controls_needed:]:
            if cursor < len(treatments):
                a, b, replicate = treatments[cursor]
                cursor += 1
                assignments.append(
                    Assignment(plate, well, "treatment", a, b, replicate)
                )
            else:
                # The design ran out before the plate did. The well is filled
                # with buffer and recorded, because an unassigned well that
                # nobody wrote down is a well somebody will later assume held
                # something.
                assignments.append(Assignment(plate, well, "unused"))

        if design.edge_policy == "exclude_perimeter":
            for well in sorted(perimeter):
                assignments.append(Assignment(plate, well, "excluded_perimeter"))

    ordered = tuple(sorted(assignments, key=lambda a: (a.plate, a.well)))
    return Layout(ordered, design.randomisation_seed, design.plate_format, plates)


def well_balance(layout: Layout, design: Design) -> list[str]:
    """Every plate must account for every well it has."""
    problems = []
    for plate in range(1, layout.plates + 1):
        counts = layout.counts(plate)
        if counts["total"] != design.plate_format:
            problems.append(
                f"plate {plate}: {counts['total']} wells assigned, "
                f"format is {design.plate_format}"
            )
        if design.edge_policy == "exclude_perimeter":
            expected = len(perimeter_wells(design.rows, design.columns))
            if counts.get("excluded_perimeter", 0) != expected:
                problems.append(
                    f"plate {plate}: {counts.get('excluded_perimeter', 0)} "
                    f"perimeter wells excluded, expected {expected}"
                )
        if counts.get("vehicle", 0) != design.controls.vehicle.wells:
            problems.append(f"plate {plate}: vehicle controls missing")
        if counts.get("untreated", 0) != design.controls.untreated.wells:
            problems.append(f"plate {plate}: untreated controls missing")
        if counts.get("blank", 0) != design.controls.blank.wells:
            problems.append(f"plate {plate}: blank controls missing")
    return problems
