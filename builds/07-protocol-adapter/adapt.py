"""The adaptation itself, which is arithmetic and a set of rules.

No model appears below this line. The model read the protocol; what a value
becomes in a different cell line is computed, and computed the same way twice.

The rule that matters is the seeding density, because it is the one Chapter 6
watches an adapter get wrong. A line that doubles every 55 h does not reach
the same confluence in 72 h as a line that doubles every 22 h, so a density
carried over unchanged produces a sparse plate, a compressed dynamic range and
an IC50 that is wrong in a direction nobody checks. The adapter either scales
it with the arithmetic shown or hands it to a person. It never carries it over
silently, and that is enforced here and asserted in the gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from extract import extract_parameters, verify
from models import (
    MANDATORY_PARAMETERS,
    Adaptation,
    AdapterError,
    ExtractedParameter,
    ParameterChange,
    TargetLine,
)
from source import SourceProtocol, load_protocol

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# A scaling this build will propose on its own. Outside it the adaptation is
# no longer a translation of the source protocol, it is a different
# experiment, and a person decides that.
SANE_SCALE = (0.2, 5.0)

HERE = Path(__file__).resolve().parent
DEFAULT_LINES = HERE / "fixtures" / "target_lines.json"


@dataclass
class AdaptationRun:
    """Everything one adaptation produced, including what it refused."""

    protocol: SourceProtocol
    target: TargetLine
    source_line: TargetLine | None
    adaptation: Adaptation
    readings: dict[str, ExtractedParameter]
    rejected_claims: list[dict[str, str]] = field(default_factory=list)


def load_lines(path: str | Path = DEFAULT_LINES) -> dict[str, TargetLine]:
    """The cell line lookup, keyed by name."""
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return {record["name"]: TargetLine(**record) for record in body["lines"]}


def _numbers(value: str | None) -> list[float]:
    return [float(n) for n in NUMBER_RE.findall(value or "")]


def _first_number(value: str | None) -> float | None:
    found = _numbers(value)
    return found[0] if found else None


def scale_seeding_density(
    source_density: float, source_doubling_h: float,
    target_doubling_h: float, endpoint_h: float,
) -> float:
    """Seed the slower line denser, by the doublings it will not get.

    In ``endpoint_h`` a line completes ``endpoint_h / doubling_time``
    doublings, so the two lines differ by that many powers of two at the
    readout. Seeding the target by that factor puts both plates at the same
    confluence when the assay is read, which is the thing the protocol was
    actually holding constant.
    """
    doublings_lost = (endpoint_h / source_doubling_h) - (endpoint_h / target_doubling_h)
    return source_density * (2.0 ** doublings_lost)


def _adapt_seeding_density(
    reading: ExtractedParameter, endpoint: ExtractedParameter,
    source_line: TargetLine | None, target: TargetLine,
) -> tuple[str, ParameterChange | None]:
    density = _first_number(reading.value)
    endpoint_h = _first_number(endpoint.value) if endpoint.stated else None

    if source_line is None:
        return "requires_human_decision", None
    if endpoint_h is None:
        return "requires_human_decision", None
    if density is None:
        return "requires_human_decision", None

    if abs(source_line.doubling_time_h - target.doubling_time_h) < 1e-9:
        return "carried_over_unchanged", None

    adapted = scale_seeding_density(
        density, source_line.doubling_time_h, target.doubling_time_h, endpoint_h,
    )
    factor = adapted / density
    if not SANE_SCALE[0] <= factor <= SANE_SCALE[1]:
        return "requires_human_decision", None

    return "changed", ParameterChange(
        parameter="seeding_density",
        source_value=str(reading.value),
        adapted_value=f"{round(adapted)} cells per well",
        rationale=(
            f"{source_line.name} doubles every {source_line.doubling_time_h:g} h "
            f"and {target.name} every {target.doubling_time_h:g} h, so over the "
            f"{endpoint_h:g} h to readout the target completes "
            f"{endpoint_h / source_line.doubling_time_h:.2f} minus "
            f"{endpoint_h / target.doubling_time_h:.2f} fewer doublings. "
            f"Seeding {factor:.2f} times denser puts both plates at the same "
            f"confluence when the assay is read. The endpoint is held, which "
            f"is itself a decision and is recorded as a carry-over."
        ),
        confidence="high",
    )


def _adapt_percentage(
    parameter: str, reading: ExtractedParameter, target_value: float,
    unit: str, rationale: str,
) -> tuple[str, ParameterChange | None]:
    stated = _first_number(reading.value)
    if stated is None:
        return "requires_human_decision", None
    if abs(stated - target_value) < 1e-9:
        return "carried_over_unchanged", None
    return "changed", ParameterChange(
        parameter=parameter,
        source_value=str(reading.value),
        adapted_value=f"{target_value:g} {unit}",
        rationale=rationale,
        confidence="high",
    )


def _adapt_passage_range(
    reading: ExtractedParameter, target: TargetLine,
) -> tuple[str, ParameterChange | None]:
    bounds = _numbers(reading.value)
    if not bounds:
        return "requires_human_decision", None
    if max(bounds) <= target.max_passage:
        return "carried_over_unchanged", None
    return "changed", ParameterChange(
        parameter="passage_number_range",
        source_value=str(reading.value),
        adapted_value=f"passage {min(bounds):g} to passage {target.max_passage}",
        rationale=(
            f"the source ran to passage {max(bounds):g}, above the "
            f"passage {target.max_passage} ceiling recorded for "
            f"{target.name}. The window is tightened rather than carried."
        ),
        confidence="high",
    )


def _adapt_readout(
    reading: ExtractedParameter, target: TargetLine,
) -> tuple[str, ParameterChange | None]:
    chemistry = (reading.value or "").lower()
    if any(flag.lower() in chemistry for flag in target.assay_interference):
        return "requires_human_decision", None
    return "carried_over_unchanged", None


def classify(
    readings: dict[str, ExtractedParameter],
    source_line: TargetLine | None,
    target: TargetLine,
) -> tuple[dict[str, str], list[ParameterChange]]:
    """Put each of the six in exactly one list, and say why where it moved."""
    placement: dict[str, str] = {}
    changes: list[ParameterChange] = []

    for parameter in MANDATORY_PARAMETERS:
        reading = readings[parameter]
        if not reading.stated:
            placement[parameter] = "not_stated_in_source"
            continue

        if parameter == "seeding_density":
            where, change = _adapt_seeding_density(
                reading, readings["incubation_to_endpoint"], source_line, target,
            )
        elif parameter == "incubation_to_endpoint":
            # Held on purpose. The readout chemistry and the plate fix the
            # endpoint far more tightly than the cell line does, so the
            # adaptation moves the density instead. Recorded as a carry-over
            # so that the decision is visible rather than assumed.
            where, change = "carried_over_unchanged", None
        elif parameter == "solvent_tolerance":
            where, change = _adapt_percentage(
                parameter, reading, target.max_dmso_pct, "% DMSO",
                f"{target.name} is recorded as tolerating no more than "
                f"{target.max_dmso_pct:g} % DMSO, which is not the source "
                "limit. Solvent tolerance is a property of the line, not of "
                "the protocol.",
            )
        elif parameter == "serum_concentration":
            where, change = _adapt_percentage(
                parameter, reading, target.serum_pct, "% foetal bovine serum",
                f"{target.name} is maintained at {target.serum_pct:g} % serum. "
                "Serum changes both growth rate and free drug concentration, "
                "so carrying the source figure over would change two things "
                "at once.",
            )
        elif parameter == "passage_number_range":
            where, change = _adapt_passage_range(reading, target)
        else:
            where, change = _adapt_readout(reading, target)

        placement[parameter] = where
        if change is not None:
            changes.append(change)

    return placement, changes


def run_adaptation(
    protocol_path: str | Path,
    target_name: str,
    client: Any,
    model: str,
    *,
    lines_path: str | Path = DEFAULT_LINES,
    trace: Any = None,
) -> AdaptationRun:
    """Read one protocol, adapt it to one line, and report the diff."""
    protocol = load_protocol(protocol_path)
    lines = load_lines(lines_path)

    if target_name not in lines:
        raise AdapterError(
            "unknown_target_line",
            f"{target_name!r} is not in the cell line records. A line with no "
            "record has no RRID and no doubling time, and neither is optional.",
        )
    target = lines[target_name]
    source_line = lines.get(protocol.cell_line)

    if trace is not None:
        trace.write("adaptation_started", doi=protocol.doi,
                    source_cell_line=protocol.cell_line,
                    target_cell_line=target.name, target_rrid=target.rrid,
                    model=model)

    extracted = extract_parameters(protocol, client, model)
    verified, rejected = verify(protocol, extracted)
    readings = {item.parameter: item for item in verified}

    if trace is not None:
        for rejection in rejected:
            trace.write("claim_rejected", **rejection)

    placement, changes = classify(readings, source_line, target)

    adaptation = Adaptation(
        source_doi=protocol.doi,
        source_cell_line=protocol.cell_line,
        target_cell_line=target.name,
        changed=changes,
        carried_over_unchanged=[p for p, where in placement.items()
                                if where == "carried_over_unchanged"],
        not_stated_in_source=[p for p, where in placement.items()
                              if where == "not_stated_in_source"],
        requires_human_decision=[p for p, where in placement.items()
                                 if where == "requires_human_decision"],
    )

    if trace is not None:
        trace.write("adaptation_complete", **adaptation.as_dict())

    return AdaptationRun(
        protocol=protocol, target=target, source_line=source_line,
        adaptation=adaptation, readings=readings, rejected_claims=rejected,
    )
