"""Build 05, the wrangler, in its own process.

The job carries the export as text and the name of an approved mapping. The
worker writes the text to a file and calls ``pipeline.run`` exactly as Build
05's own tests do, because the question is what that function does, not what a
reimplementation of it would do.

The six assertions and the schema are the checks. Each is reported under the
name Build 05 gives it, so a fault that says it should be caught by
``identifier_integrity`` is naming a function that exists in another folder:

    row_conservation      wells in equals rows out
    silent_nulls          a value that became null without being declared
    units_declared        a numeric column whose name carries no unit
    range_plausibility    a value outside the declared bounds
    identifier_integrity  a well that is not on the plate map
    determinism           two runs of the same input disagreeing
    schema                the printed pandera schema refusing the frame
    transform             the mapping does not fit the file
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BUILD))

import pipeline
from assertions import (
    DeterminismFailed,
    Expectation,
    IdentifierIntegrityFailed,
    RangePlausibilityFailed,
    RowConservationFailed,
    SilentNullsFailed,
    UnitDeclarationFailed,
)
from transform import TransformError
from validate import SchemaError

# Build 05 names its refusals with classes. This is the only translation
# between its vocabulary and the harness's, and it is one line per assertion
# so that a rename over there shows up as a KeyError here rather than as a
# detection rate that quietly fell.
CHECK_FOR = {
    RowConservationFailed: "row_conservation",
    SilentNullsFailed: "silent_nulls",
    UnitDeclarationFailed: "units_declared",
    RangePlausibilityFailed: "range_plausibility",
    IdentifierIntegrityFailed: "identifier_integrity",
    DeterminismFailed: "determinism",
    SchemaError: "schema",
    TransformError: "transform",
    pipeline.UnitCollision: "units_declared",
}


def check_name(error: BaseException) -> str:
    for kind, name in CHECK_FOR.items():
        if isinstance(error, kind):
            return name
    return "unclassified"


def handle(job, workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    export = workspace / "export.csv"
    export.write_text(job["csv"], encoding="utf-8", newline="\n")

    mapping = pipeline.load_mapping(BUILD / "mappings" / job["mapping"])
    expected = Expectation(wells=job.get("expected_wells", 6))

    events = ["transform_started"]
    try:
        result = pipeline.run(export, mapping, expected)
    except Exception as error:  # noqa: BLE001 - classified, then reported
        return {
            "status": "FAILED",
            "checks_fired": [check_name(error)],
            "events": events,
            "answer": None,
            "detail": f"{type(error).__name__}: {error}",
        }

    frame = result.pop("frame")
    events.append("table_written")
    concentrations = sorted(float(value) for value in frame["conc_nM"])
    return {
        "status": "COMPLETE",
        "checks_fired": [],
        "events": events,
        "answer": {
            "rows": result["rows"],
            "wells": result["wells"],
            "conc_nM_min": concentrations[0],
            "conc_nM_max": concentrations[-1],
        },
        "detail": f"{result['rows']} rows, nothing refused it",
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, line in enumerate(sys.stdin):
            if not line.strip():
                continue
            try:
                result = handle(json.loads(line), root / f"job{index}")
            except Exception as error:  # noqa: BLE001
                result = {"status": "FAILED", "checks_fired": [], "events": [],
                          "answer": None,
                          "detail": f"{type(error).__name__}: {error}"}
            sys.stdout.write(json.dumps(result, default=str) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
