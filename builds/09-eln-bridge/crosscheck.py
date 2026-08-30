"""The numeric cross-check, which runs before a human sees the diff.

This is the most important module in the build, and the reason is in the
chapter's failure account rather than in anything about the code. An injected
instruction changed the concentrations in a proposed entry, the gate caught
it, and the gate caught it because the author happened to know those
concentrations by heart. Had the injection changed a passage number or a
supplier lot, it would have been approved. The control that worked was a
person's memory on a good morning, and that is not a control.

So every number in a proposal is put next to the design file before anybody
looks at the diff, and the result is attached to the diff rather than offered
as a separate report somebody has to go and open.

There are two outcomes worth distinguishing and the second one is the point:

``MISMATCH``
    the design states a value and the proposal contradicts it. This is the
    chapter's case, and it is caught by arithmetic rather than by recall.

``UNVERIFIABLE``
    the proposal states a number and the design says nothing about it. A
    passage number, a supplier lot, an incubation time. Nothing here can check
    these, and the honest response is to say so in the diff rather than to let
    them through silently. A number the system cannot check is exactly the
    number an injection would choose, so the reviewer is told which numbers
    they are being asked to take on trust. It does not make them right. It
    makes the trust visible, and it is the difference between a reviewer who
    knows what they are vouching for and one who does not.

The arithmetic is Python's. Dilution series are computed here, unit conversion
is done here, and no part of any of it is asked of a model.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

# Concentrations are floats off a dilution series, so equality is the wrong
# test. Half a per cent is tight enough that a doubling or a decimal slip
# cannot hide in it, and loose enough that 0.078125 written as 0.0781 passes.
RELATIVE_TOLERANCE = 0.005

# Everything normalises to micromolar, in Python, once.
TO_MICROMOLAR = {
    "m": 1_000_000.0, "mm": 1_000.0, "um": 1.0, "µm": 1.0, "μm": 1.0,
    "nm": 0.001, "pm": 0.000001,
}

CONCENTRATION_IN_TEXT = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(mM|uM|µM|μM|nM|pM|M)(?![\w])"
)

# Numbers that are not concentrations, recognised only so the report can name
# what kind of number it is declining to verify.
UNCHECKABLE_KINDS = (
    ("passage_number", re.compile(r"\b(?:passage|pass\.?|p)\s*[.:]?\s*(\d+)\b",
                                  re.IGNORECASE)),
    ("supplier_lot", re.compile(r"\b(?:lot|batch)\s*[.:#]?\s*([\w-]*\d[\w-]*)",
                                re.IGNORECASE)),
    ("incubation_time", re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:h|hr|hours|min|"
                                   r"minutes)\b", re.IGNORECASE)),
    ("temperature_C", re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:°C|degC|C)\b")),
    ("volume_uL", re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:uL|µL|μL|mL)\b",
                             re.IGNORECASE)),
    ("cell_count", re.compile(r"\b(\d[\d,]{2,})\s*cells\b", re.IGNORECASE)),
)


class CrossCheckError(RuntimeError):
    """The design this proposal cites cannot be read."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


class Axis(BaseModel):
    """One dose axis, in Build 06's shape.

    Copied rather than imported. Build 06 owns the design format and validates
    it; this build reads one for a single purpose, so ``extra="ignore"`` lets
    the same committed YAML load here without this file claiming to be a
    second validator of it.
    """

    model_config = ConfigDict(extra="ignore")

    name: str
    top_conc_uM: float = Field(gt=0)
    dilution_factor: float = Field(gt=1)
    n_steps: int = Field(ge=2, le=24)

    def series_uM(self) -> list[float]:
        return [self.top_conc_uM / (self.dilution_factor ** step)
                for step in range(self.n_steps)]


class Design(BaseModel):
    model_config = ConfigDict(extra="ignore")

    design_id: str
    cell_line: str
    axes: dict[str, Axis]

    def concentrations_uM(self) -> dict[str, list[float]]:
        """Every concentration the design actually delivers, per agent."""
        return {axis.name.lower(): axis.series_uM() for axis in self.axes.values()}

    def all_concentrations_uM(self) -> list[float]:
        out: list[float] = []
        for series in self.concentrations_uM().values():
            out.extend(series)
        return sorted(set(out))


class NumericFinding(BaseModel):
    """One number in a proposal, and what the design had to say about it."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["MATCH", "MISMATCH", "UNVERIFIABLE"]
    code: str
    quantity: str
    stated: str
    stated_uM: float | None = None
    nearest_in_design_uM: float | None = None
    detail: str

    @property
    def is_flag(self) -> bool:
        return self.verdict != "MATCH"

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.verdict, "code": self.code,
                "quantity": self.quantity, "stated": self.stated,
                "detail": self.detail}


def load_design(path: str | Path) -> Design:
    path = Path(path)
    try:
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise CrossCheckError("design_unreadable", f"{path}: {error}") from error
    if not isinstance(body, dict):
        raise CrossCheckError("design_unreadable", f"{path} is not a mapping")
    return Design(**body)


def find_design(design_id: str, designs_dir: str | Path) -> Design:
    for path in sorted(Path(designs_dir).glob("*.yaml")):
        design = load_design(path)
        if design.design_id == design_id:
            return design
    raise CrossCheckError(
        "design_not_found",
        f"no design file declares design_id {design_id!r} under {designs_dir}",
    )


def to_micromolar(value: float, unit: str) -> float:
    """Unit conversion, in Python. A model is never asked to do this."""
    factor = TO_MICROMOLAR.get(unit.lower())
    if factor is None:
        raise CrossCheckError("unknown_unit", f"cannot convert {unit!r}")
    return value * factor


def _matches(value_uM: float, candidates: list[float]) -> float | None:
    """The design value this one agrees with, or None."""
    for candidate in candidates:
        if abs(value_uM - candidate) <= RELATIVE_TOLERANCE * max(candidate, 1e-12):
            return candidate
    return None


def _nearest(value_uM: float, candidates: list[float]) -> float | None:
    return min(candidates, key=lambda c: abs(c - value_uM)) if candidates else None


def _structured_values(payload: dict) -> list[tuple[str, float, str, str]]:
    """Values the proposal states as data rather than as prose.

    Units live in the key, as they do in every column name in Build 05, so
    ``conc_nM: 12500`` carries its own unit and there is nothing to infer.
    """
    out = []
    for item in payload.get("values", []) or []:
        name = str(item.get("name", "unnamed"))
        for key, raw in item.items():
            if key == "name" or "_" not in key:
                continue
            unit = key.rsplit("_", 1)[1]
            if unit.lower() not in TO_MICROMOLAR:
                continue
            out.append((name, float(raw), unit, f"{raw} {unit}"))
    return out


def check_proposal(payload: dict, design: Design | None) -> list[NumericFinding]:
    """Every number in a proposal, checked against the design that governs it.

    Runs with no human input. That is the requirement: the flags are on the
    diff before it is displayed, not raised by a reviewer who noticed.
    """
    findings: list[NumericFinding] = []
    text = "\n".join(
        str(payload.get(field, "")) for field in ("title", "body", "summary")
    )

    if design is None:
        findings.append(NumericFinding(
            verdict="UNVERIFIABLE", code="no_design_reference",
            quantity="the whole proposal", stated="",
            detail="the proposal cites no design file, so no number in it can "
                   "be checked against anything. Every value below is being "
                   "taken on trust.",
        ))

    by_agent = design.concentrations_uM() if design else {}
    every = design.all_concentrations_uM() if design else []

    stated: list[tuple[str, float, str, str]] = list(_structured_values(payload))
    for match in CONCENTRATION_IN_TEXT.finditer(text):
        value, unit = float(match.group(1)), match.group(2)
        stated.append((_agent_near(text, match.start(), by_agent),
                       value, unit, match.group(0)))

    for name, value, unit, as_written in stated:
        value_uM = to_micromolar(value, unit)
        candidates = by_agent.get(name.lower(), every)
        if design is None or not candidates:
            findings.append(NumericFinding(
                verdict="UNVERIFIABLE", code="no_reference_value",
                quantity=name, stated=as_written, stated_uM=value_uM,
                detail="the design states no concentration series for this, "
                       "so the value cannot be confirmed or contradicted",
            ))
            continue
        hit = _matches(value_uM, candidates)
        if hit is not None:
            findings.append(NumericFinding(
                verdict="MATCH", code="agrees_with_design", quantity=name,
                stated=as_written, stated_uM=value_uM,
                nearest_in_design_uM=hit,
                detail=f"the design delivers {hit:g} uM on this axis",
            ))
        else:
            findings.append(NumericFinding(
                verdict="MISMATCH", code="concentration_absent_from_design",
                quantity=name, stated=as_written, stated_uM=value_uM,
                nearest_in_design_uM=_nearest(value_uM, candidates),
                detail=f"design {design.design_id} delivers no such "
                       f"concentration on this axis. The series is "
                       f"{', '.join(f'{c:g}' for c in sorted(candidates, reverse=True))} uM.",
            ))

    findings.extend(_uncheckable(text))
    return findings


def _agent_near(text: str, position: int, by_agent: dict[str, list[float]]) -> str:
    """Which agent a concentration in prose is talking about.

    Looks backwards over the same sentence for a name the design knows. It is
    a heuristic and it can be wrong, which is why being wrong here downgrades
    a value to the whole-design series rather than silently passing it.
    """
    window = text[max(0, position - 120): position + 60].lower()
    for name in by_agent:
        if name in window:
            return name
    return "unnamed"


def _uncheckable(text: str) -> list[NumericFinding]:
    """Numbers the design says nothing about, named rather than ignored.

    This is the chapter's passage number. It is not verified here and this
    module does not pretend otherwise; it is listed so that the reviewer is
    told which numbers they are being asked to take on trust.
    """
    findings = []
    for kind, pattern in UNCHECKABLE_KINDS:
        for match in pattern.finditer(text):
            findings.append(NumericFinding(
                verdict="UNVERIFIABLE", code=f"unverifiable_{kind}",
                quantity=kind, stated=match.group(0).strip(),
                detail="the design file carries no reference for this, so it "
                       "is being taken on trust. An injection choosing a "
                       "number the system cannot check would choose this one.",
            ))
    return findings


def summarise(findings: list[NumericFinding]) -> dict[str, Any]:
    """The counts, for the trace and for the head of the diff."""
    mismatches = [f for f in findings if f.verdict == "MISMATCH"]
    unverifiable = [f for f in findings if f.verdict == "UNVERIFIABLE"]
    return {
        "status": "FLAGGED" if mismatches or unverifiable else "CLEAN",
        "code": "numeric_mismatch" if mismatches else (
            "numbers_taken_on_trust" if unverifiable else "all_values_agree"),
        "checked": len(findings),
        "mismatches": len(mismatches),
        "unverifiable": len(unverifiable),
        "detail": [finding.as_dict() for finding in findings if finding.is_flag],
    }
