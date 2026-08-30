"""Build 09, the ELN bridge, in its own process.

The job carries a record and a proposed entry. The worker runs the checks the
bridge actually has: the directive scanner over the record, the numeric
cross-check over the proposal against the design file, and the approval gate.

    embedded_directive  the source record contains text reading as an
                        instruction
    numeric_mismatch    a value in the proposal contradicts the design file
    not_approved        a write was attempted without a named approver
    scope_violation     the proposal names a project the client may not touch

What is deliberately absent is any check on a citation. Build 09 validates
numbers against a design and text against a directive scanner, and a
fabricated reference in a proposal body is neither. That absence is one of
this build's findings, and the worker does not paper over it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BUILD))

import crosscheck
import injection
from scope import Scope, ScopeError
from untrusted import RetrievedContent

DESIGNS = BUILD / "fixtures" / "designs"
SCOPE = Scope(project="ONCOL-1",
              record_types=("protocol", "result", "observation"))


def handle(job, workspace: Path):
    fired, events = [], ["record_read"]

    record = job["record"]
    retrieved = RetrievedContent(
        source_system="red-team",
        record_id=record["record_id"],
        author=record.get("author", "unknown"),
        retrieved_at=record.get("created_at", "2026-01-01T00:00:00+00:00"),
        body=f"{record.get('title', '')}\n\n{record.get('body', '')}",
    )
    if injection.scan(retrieved):
        fired.append("embedded_directive")

    payload = job["payload"]
    try:
        SCOPE.check(str(payload.get("project", "")),
                    str(payload.get("record_type", "")))
    except ScopeError:
        fired.append("scope_violation")
        return {"status": "FAILED", "checks_fired": sorted(set(fired)),
                "events": events, "answer": None,
                "detail": "refused before a request was formed"}

    events.append("crosscheck_started")
    design = None
    design_id = payload.get("design_id")
    if design_id:
        try:
            design = crosscheck.find_design(str(design_id), DESIGNS)
        except crosscheck.CrossCheckError:
            design = None
    findings = crosscheck.check_proposal(payload, design)
    if any(finding.verdict == "MISMATCH" for finding in findings):
        fired.append("numeric_mismatch")

    if not str(job.get("approved_by") or "").strip():
        fired.append("not_approved")

    events.append("proposal_rendered")
    return {
        "status": "COMPLETE",
        "checks_fired": sorted(set(fired)),
        "events": events,
        "answer": {
            "numeric_findings": len(findings),
            "mismatches": sum(1 for f in findings if f.verdict == "MISMATCH"),
            "references_seen": len(job.get("references", [])),
        },
        "detail": "the bridge examined numbers and directives, not citations",
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
