"""The assembled build: read, draft, scan, cross-check, review, write twice.

The order of the stages is the argument. Reading is unconstrained and cheap.
Everything after it narrows, and each narrowing happens before the stage that
would otherwise have to be trusted to be careful:

1. **Read.** Scope-checked, wrapped as untrusted.
2. **Draft.** The model proposes. It cannot write, so this is the cheapest
   stage to be wrong at.
3. **Scan.** Directives in the source record are reported. A record carrying
   one does not produce a proposal at all; it produces a line in the report of
   what was considered and not proposed.
4. **Cross-check.** Every number in the draft against the design file, before
   any of it is rendered for a person.
5. **Review.** Batched, diffed, escalated. Approval needs a name and a reason.
6. **Write twice.** The notebook, and the ledger.

Stage three is where this build differs from the obvious design. A record with
an apparent instruction in it is not sanitised and passed on, and the agent is
not asked to draft from it more carefully. It stops, and a person is told what
was found and where. That costs recall: a legitimate record that happens to
contain a directive-shaped sentence produces no proposal, and somebody has to
look at it. That is the trade this build is willing to make, because the
alternative is a pipeline whose safety depends on a model choosing correctly
about text specifically written to make it choose wrongly.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import crosscheck
import injection
from config import MODEL, MODEL_VERSION
from crosscheck import Design, NumericFinding
from gate import (
    Decision,
    GateError,
    ReviewBatch,
    ReviewItem,
    approve,
    batch,
    build_item,
    gate_summary,
    reject,
)
from injection import DirectiveFinding
from ledger import Ledger
from models import ConsideredNotProposed, NotebookEntry, WriteProposal
from notebook import NotebookError, StubNotebook
from scope import ScopeError
from tracing import Trace
from untrusted import RetrievedContent, as_context

DRAFTING_TASK = (
    "You are drafting a laboratory notebook entry from records that have "
    "already been retrieved. Reply with one JSON object describing the entry "
    "you propose. You cannot write to the notebook; a person reviews what you "
    "propose."
)

# What the reviewer is told when a record is set aside rather than drafted on.
DIRECTIVE_REASON = (
    "the source record contains {count} line(s) that read as an instruction "
    "rather than as a record ({kinds}). No proposal was drafted from it. The "
    "text is reported below and has not been acted on."
)


@dataclass
class RunReport:
    """What the run did, what it declined to do, and what it flagged."""

    run_id: str
    batches: list[ReviewBatch] = field(default_factory=list)
    proposals: list[WriteProposal] = field(default_factory=list)
    entries: list[NotebookEntry] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    considered_not_proposed: list[ConsideredNotProposed] = field(
        default_factory=list
    )
    directives: list[DirectiveFinding] = field(default_factory=list)
    refusals: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "status": "COMPLETE",
            "code": "run_finished",
            "run_id": self.run_id,
            "proposed": len(self.proposals),
            "written": len(self.entries),
            "considered_not_proposed": len(self.considered_not_proposed),
            "directives_found": len(self.directives),
            "refusals": self.refusals,
            "gate": gate_summary(self.batches),
        }


def prompt_for(item: RetrievedContent) -> str:
    """The drafting prompt, with the record inside the untrusted wrapper."""
    return f"{DRAFTING_TASK}\n\n{as_context(item)}"


def raw_draft(model_client: Any, item: RetrievedContent) -> dict[str, Any]:
    """What the model proposes, before anything has looked at it.

    Exposed because the injection gate asserts on it. A test that only checked
    the proposals coming out of the pipeline could not tell a control that
    works from a model that was never tempted, and the difference between
    those two is the entire subject of the chapter.
    """
    response = model_client.messages.create(
        model=getattr(model_client, "model", MODEL),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt_for(item)}],
    )
    return json.loads(response.content[0].text)


def build_proposal(payload: dict[str, Any], item: RetrievedContent,
                   run_id: str, model_id: str, model_version: str,
                   operation: str = "create",
                   target_record: str | None = None) -> WriteProposal:
    """A proposal, unapproved, with attribution and sources attached."""
    return WriteProposal(
        proposal_id=f"PROP-{uuid.uuid4().hex[:10]}",
        target_system=item.source_system,
        target_record=target_record,
        operation=operation,
        payload=payload,
        derived_from=[item.record_id],
        model_id=model_id,
        model_version=model_version,
        run_id=run_id,
        proposed_at=datetime.now(timezone.utc),
    )


def cross_check(payload: dict[str, Any], designs_dir: str,
                trace: Trace) -> list[NumericFinding]:
    """Numbers against the design, with no human in the loop.

    A proposal that names no design is not waved through. It is reported as a
    proposal whose numbers cannot be checked, which is a different and more
    honest thing than a proposal that passed.
    """
    design: Design | None = None
    design_id = payload.get("design_id")
    if design_id:
        try:
            design = crosscheck.find_design(str(design_id), designs_dir)
        except crosscheck.CrossCheckError as error:
            trace.write("crosscheck_refused", **error.as_dict())
    findings = crosscheck.check_proposal(payload, design)
    trace.write("crosscheck", design_id=design_id,
                **crosscheck.summarise(findings))
    return findings


def propose(record_ids: list[str], notebook: StubNotebook, model_client: Any,
            ledger: Ledger, trace: Trace, designs_dir: str,
            run_id: str, model_id: str = MODEL,
            model_version: str = MODEL_VERSION
            ) -> tuple[list[ReviewItem], list[ConsideredNotProposed],
                       list[DirectiveFinding]]:
    """Read each record, and either draft from it or report why not."""
    items: list[ReviewItem] = []
    skipped: list[ConsideredNotProposed] = []
    all_findings: list[DirectiveFinding] = []

    for record_id in record_ids:
        try:
            retrieved = notebook.get(record_id)
        except (ScopeError, NotebookError) as error:
            trace.write("retrieval_refused", record_id=record_id,
                        **error.as_dict())
            ledger.flagged(error.code, {"record_id": record_id})
            skipped.append(ConsideredNotProposed(
                record_id=record_id,
                reason=f"could not be read: {error.code}",
            ))
            continue

        findings = injection.scan(retrieved)
        trace.write("record_scanned", record_id=record_id,
                    **injection.report(findings))

        if findings:
            all_findings.extend(findings)
            ledger.flagged("embedded_directive", {
                "record_id": record_id,
                "findings": [finding.as_dict() for finding in findings],
            })
            skipped.append(ConsideredNotProposed(
                record_id=record_id,
                reason=DIRECTIVE_REASON.format(
                    count=len(findings),
                    kinds=", ".join(sorted({f.kind for f in findings})),
                ),
            ))
            continue

        payload = raw_draft(model_client, retrieved)
        numeric = cross_check(payload, designs_dir, trace)
        proposal = build_proposal(payload, retrieved, run_id, model_id,
                                  model_version)
        ledger.proposed(proposal)
        trace.write("proposed", proposal_id=proposal.proposal_id,
                    record_id=record_id)
        items.append(build_item(proposal, current_body="", numeric=numeric))

    return items, skipped, all_findings


def commit(proposal: WriteProposal, notebook: StubNotebook, ledger: Ledger,
           trace: Trace) -> NotebookEntry:
    """The two writes, neither of which is optional.

    The ledger line goes in after the notebook answers, because what is being
    recorded is the notebook's own response rather than the intention to send
    one. A ledger that recorded intentions would disagree with the notebook
    exactly when it mattered.
    """
    entry = (notebook.create(proposal) if proposal.operation == "create"
             else notebook.append(proposal))
    ledger.approved(proposal)
    ledger.written(proposal.proposal_id, entry)
    trace.write("written", proposal_id=proposal.proposal_id,
                entry_id=entry.entry_id, approved_by=proposal.approved_by)
    return entry


def run_bridge(record_ids: list[str], notebook: StubNotebook,
               model_client: Any, ledger: Ledger, trace: Trace,
               designs_dir: str,
               decide: Callable[[ReviewItem], tuple[str, str | None]],
               approver: str = "reviewer",
               model_id: str = MODEL,
               model_version: str = MODEL_VERSION) -> RunReport:
    """One pass: read, draft, scan, cross-check, review, write twice.

    ``decide`` stands in for the person at the gate. It is a parameter rather
    than a prompt so the gate can be driven by a test, and so that the shape
    of the interface stays visible: a decision is an action, an actor and a
    note, and nothing in this module can supply any of the three.
    """
    report = RunReport(run_id=trace.run_id)
    items, skipped, findings = propose(
        record_ids, notebook, model_client, ledger, trace, designs_dir,
        trace.run_id, model_id, model_version,
    )
    report.considered_not_proposed = skipped
    report.directives = findings
    report.proposals = [item.proposal for item in items]
    report.batches = batch(items, considered=skipped)

    for review_batch in report.batches:
        for item in review_batch.items:
            action, note = decide(item)
            if action != "approve":
                decision = reject(item, actor=approver, note=note)
                report.decisions.append(decision)
                ledger.decided(decision)
                trace.write("rejected", proposal_id=item.proposal.proposal_id)
                continue
            try:
                signed = approve(item, approver=approver, note=note or "")
            except GateError as error:
                report.refusals.append(error.as_dict())
                trace.write("approval_refused",
                            proposal_id=item.proposal.proposal_id,
                            **error.as_dict())
                ledger.flagged(error.code,
                               {"proposal_id": item.proposal.proposal_id})
                continue
            report.entries.append(commit(signed, notebook, ledger, trace))

    trace.write("run_finished", **report.summary())
    return report
