"""Arithmetic in Python, before the pipette.

Every number here is computed. None of it is asked of a model. The three
problems this catches are all cheap to check and all expensive to discover
after the cells are gone.
"""

# Reported IC50 in micromolar for the lines this design targets. These are
# the floor a series has to reach below: a curve whose lowest dose sits above
# the IC50 has no lower plateau, so the fitted value is an extrapolation and
# nobody finds out until the experiment is over.
#
# Values are the midpoint of the ranges quoted in the Chapter 6 references for
# U87MG. They are deliberately in one place: a design that targets a different
# line needs its own entry rather than a silent reuse of this one.
EXPECTED_IC50 = {
    "temozolomide": 100.0,
    "nanaomycin_A": 0.5,
}

# The smallest volume an air-displacement pipette delivers with acceptable
# precision. Below roughly two microlitres the coefficient of variation climbs
# steeply, so a serial dilution built on smaller transfers compounds an error
# at every step.
MIN_RELIABLE_UL = 2.0


def check_dilution_series(drug: str, top_uM: float, factor: float,
                          n: int, stock_mM: float, transfer_uL: float,
                          max_solvent_pct: float) -> list[str]:
    problems = []
    series = [top_uM / (factor ** i) for i in range(n)]

    # 1. Does the top concentration require more solvent than cells tolerate?
    solvent_pct = (top_uM / (stock_mM * 1000)) * 100
    if solvent_pct > max_solvent_pct:
        problems.append(
            f"Top dose needs {solvent_pct:.2f}% solvent, "
            f"limit is {max_solvent_pct}%")

    # 2. Is the lowest dose still above the reported IC50 floor?
    if series[-1] > EXPECTED_IC50[drug]:
        problems.append("Series never drops below the expected IC50; "
                        "the curve will have no lower plateau")

    # 3. Is the serial transfer volume below what the pipette can deliver?
    if transfer_uL < MIN_RELIABLE_UL:
        problems.append("Serial transfer below reliable pipetting volume")

    return problems
