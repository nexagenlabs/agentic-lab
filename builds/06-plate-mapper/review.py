"""Every check this build makes about a design, in one call.

Ordered cheapest first, and structural before physical, so that a failure
names the thing that is wrong rather than the first thing that noticed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from checks import check_dilution_series
from commitment import CommitmentError, check_commitment_precedes_data
from design import Design, DesignError, load_design
from layout import build_layout, well_balance

# Defaults for the bench parameters a design does not carry. A design that
# needs different ones states them; these are the values the printed design
# was written against.
DEFAULT_STOCK_MM = 100.0
DEFAULT_TRANSFER_UL = 100.0


class ReviewFailed(RuntimeError):
    """A design failed review, carrying which check refused it."""

    def __init__(self, failure: str, detail: str) -> None:
        super().__init__(f"{failure}: {detail}")
        self.failure = failure
        self.detail = detail


def review_design(
    design_path: str | Path,
    *,
    results_dir: str | Path | None = None,
    stock_mM: float = DEFAULT_STOCK_MM,
    transfer_uL: float = DEFAULT_TRANSFER_UL,
    max_solvent_pct: float | None = None,
) -> dict[str, Any]:
    """Review a design, raising ``ReviewFailed`` on the first refusal."""
    try:
        design: Design = load_design(design_path)
    except DesignError as error:
        raise ReviewFailed(error.failure, error.detail) from error

    limit = (
        max_solvent_pct
        if max_solvent_pct is not None
        else design.controls.vehicle.final_pct
    )

    problems: list[str] = []
    for axis in design.axes.values():
        problems.extend(
            check_dilution_series(
                axis.name, axis.top_conc_uM, axis.dilution_factor,
                axis.n_steps, stock_mM, transfer_uL, limit,
            )
        )

    for problem in problems:
        if "solvent" in problem:
            raise ReviewFailed("solvent_above_tolerance", problem)
    for problem in problems:
        if "pipetting" in problem:
            raise ReviewFailed("transfer_below_minimum", problem)
    for problem in problems:
        if "plateau" in problem:
            raise ReviewFailed("no_lower_plateau", problem)

    try:
        layout = build_layout(design)
    except ValueError as error:
        raise ReviewFailed("wells_do_not_balance", str(error)) from error

    imbalance = well_balance(layout, design)
    if imbalance:
        raise ReviewFailed("wells_do_not_balance", "; ".join(imbalance))

    commitment = None
    if results_dir is not None:
        try:
            commitment = check_commitment_precedes_data(design_path, results_dir)
        except CommitmentError as error:
            raise ReviewFailed(error.failure, error.detail) from error
        except DesignError as error:
            raise ReviewFailed(error.failure, error.detail) from error

    return {
        "design_id": design.design_id,
        "plates": layout.plates,
        "treatment_wells": design.treatment_wells,
        "dilution_problems": problems,
        "commitment": commitment,
    }
