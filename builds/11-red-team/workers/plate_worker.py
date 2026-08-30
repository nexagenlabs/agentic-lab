"""Build 06, the plate mapper, in its own process.

The job carries a design as a mapping. The worker writes it as YAML and calls
``review_design``, which is what a reader runs. ``ReviewFailed`` carries the
name of the check that refused, so the translation here is one line: the check
name reported to the harness is the name Build 06 already uses.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml

BUILD = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BUILD))

from design import DesignError
from review import ReviewFailed, review_design


def handle(job, workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / "design.yaml"
    path.write_text(yaml.safe_dump(job["design"], sort_keys=False),
                    encoding="utf-8", newline="\n")

    events = ["review_started"]
    try:
        result = review_design(path)
    except (ReviewFailed, DesignError) as error:
        return {
            "status": "FAILED",
            "checks_fired": [getattr(error, "failure", "unclassified")],
            "events": events,
            "answer": None,
            "detail": str(error),
        }

    events.append("layout_written")
    return {
        "status": "COMPLETE",
        "checks_fired": [],
        "events": events,
        "answer": {"wells": result.get("wells"),
                   "design_id": result.get("design_id")},
        "detail": "the design passed review",
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
