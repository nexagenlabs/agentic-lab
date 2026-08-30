"""Table 8.2: the approval gate, built as a review rather than as a prompt.

A confirmation dialogue is not a gate. It asks a yes or no question about text
somebody has not read, at the moment they are least able to read it, and after
the fortieth one the answer is always yes. Everything in this module exists to
make the review a thing a tired person can actually do at nine in the morning.

Five properties, each of which is a line in the chapter's table:

**A diff, not the proposed text.** Showing what the entry will say tells you
nothing about what changes. Showing what changes is the whole question, and
for an append against a long record it is the difference between two lines and
two pages.

**Approve, reject, edit. Rejection needs no explanation; approval does.** That
asymmetry is deliberate and it is the opposite of most systems. Making
rejection cheap and approval slightly expensive puts the friction on the
action that writes to a laboratory record. A reviewer who has to type why
cannot approve forty things in ninety seconds, and that is the intent rather
than a side effect.

**Batches hold one kind, and never more than a screenful.** Mixing a create
among nine appends is how the create gets approved. Scrolling is how the tenth
item gets approved unread.

**Escalation.** A routine append is quiet. Anything touching a numeric result
is highlighted, and the numeric cross-check has already run against the design
file before the reviewer sees any of it.

**What was considered and not proposed.** The Chapter 6 principle again. An
agent that lists only its actions lets you walk past everything it decided
against, and the decision not to write about the one anomalous record is
invisible in a list of the four ordinary ones it did write about.
"""

from __future__ import annotations

import difflib
from datetime import datetime, timezone
from typing import Any, Literal

from crosscheck import NumericFinding, summarise
from injection import DirectiveFinding
from models import ConsideredNotProposed, WriteProposal
from pydantic import BaseModel, ConfigDict, Field

# One screen, honestly counted. Ten proposals with a diff each is already more
# than fits on a laptop, and a batch that needs scrolling has an item at the
# bottom that gets approved without being read.
SCREENFUL = 8


class GateError(RuntimeError):
    """The gate refused to record a decision."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


class DiffLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker: Literal[" ", "+", "-"]
    text: str


class ReviewItem(BaseModel):
    """One proposal, with everything a reviewer needs attached to it.

    The findings are attached rather than reported separately on purpose. A
    numeric mismatch in a report somebody has to open is a numeric mismatch
    nobody opens.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    proposal: WriteProposal
    diff: list[DiffLine]
    numeric: list[NumericFinding] = Field(default_factory=list)
    directives: list[DirectiveFinding] = Field(default_factory=list)

    @property
    def kind(self) -> str:
        """Proposals batch together only when this matches."""
        return f"{self.proposal.operation}:{self.proposal.payload.get('record_type', 'unknown')}"

    @property
    def escalation(self) -> Literal["routine", "highlighted"]:
        """Quiet for a routine append, highlighted for anything numeric.

        A directive found in a source record highlights the item too. The
        agent read something that read as an instruction, and the reviewer
        should know that before deciding what the proposal means.
        """
        if any(finding.is_flag for finding in self.numeric):
            return "highlighted"
        if self.directives:
            return "highlighted"
        if self.proposal.payload.get("values"):
            return "highlighted"
        if self.proposal.payload.get("record_type") == "result":
            return "highlighted"
        return "routine"

    @property
    def blocking(self) -> list[NumericFinding]:
        return [f for f in self.numeric if f.verdict == "MISMATCH"]

    def render(self) -> str:
        """The item as a reviewer sees it. Flags first, then the diff."""
        target = self.proposal.target_record or "(new record)"
        sources = ", ".join(self.proposal.derived_from) or "nothing recorded"
        head = [
            f"[{self.escalation.upper()}] {self.proposal.operation} {target}",
            f"  proposal {self.proposal.proposal_id}, derived from {sources}",
        ]
        for finding in self.numeric:
            if finding.is_flag:
                head.append(
                    f"  ! {finding.verdict} {finding.quantity}: "
                    f"{finding.stated}, {finding.detail}"
                )
        for finding in self.directives:
            head.append(
                f"  ! DIRECTIVE in {finding.record_id} line "
                f"{finding.line_number}: {finding.excerpt}"
            )
        body = [f"  {line.marker} {line.text}" for line in self.diff]
        return "\n".join(head + body)


class ReviewBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    items: list[ReviewItem]
    considered_not_proposed: list[ConsideredNotProposed] = Field(
        default_factory=list
    )

    def render(self) -> str:
        lines = [f"=== {len(self.items)} x {self.kind} ==="]
        lines.extend(item.render() for item in self.items)
        lines.append("")
        lines.append(
            f"Considered and not proposed: {len(self.considered_not_proposed)}"
        )
        for skipped in self.considered_not_proposed:
            lines.append(f"  - {skipped.record_id}: {skipped.reason}")
        return "\n".join(lines)


class Decision(BaseModel):
    """What a reviewer did, kept whether or not anything was written.

    A rejection is recorded as carefully as an approval. The ledger's job is
    to say what the agent proposed and what happened to it, and a proposal
    that vanished because somebody said no is a thing worth being able to find
    six months later.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    action: Literal["approve", "reject", "edit"]
    actor: str
    note: str | None
    at: datetime


def build_diff(current_body: str, proposed_body: str) -> list[DiffLine]:
    """What changes, marked, rather than what the entry will say.

    An append is shown as an addition against the record as it stands, so a
    reviewer sees two new lines rather than the whole record with two new
    lines somewhere in it.
    """
    current = current_body.split("\n") if current_body else []
    proposed = proposed_body.split("\n") if proposed_body else []
    out: list[DiffLine] = []
    matcher = difflib.SequenceMatcher(a=current, b=proposed, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Context, trimmed. A reviewer needs the join, not the record.
            for line in current[i1:i2][-2:]:
                out.append(DiffLine(marker=" ", text=line))
        else:
            for line in current[i1:i2]:
                out.append(DiffLine(marker="-", text=line))
            for line in proposed[j1:j2]:
                out.append(DiffLine(marker="+", text=line))
    return out


def build_item(proposal: WriteProposal, current_body: str,
               numeric: list[NumericFinding] | None = None,
               directives: list[DirectiveFinding] | None = None) -> ReviewItem:
    """Assemble one reviewable item. The findings are already computed."""
    appended = str(proposal.payload.get("body", ""))
    proposed_body = (
        f"{current_body}\n\n{appended}" if proposal.operation == "append"
        and current_body else appended
    )
    return ReviewItem(
        proposal=proposal,
        diff=build_diff(current_body, proposed_body),
        numeric=list(numeric or []),
        directives=list(directives or []),
    )


def batch(items: list[ReviewItem],
          considered: list[ConsideredNotProposed] | None = None,
          screenful: int = SCREENFUL) -> list[ReviewBatch]:
    """Group by kind, split at a screenful, never mix.

    ``considered_not_proposed`` is attached to every batch rather than to one
    of them, because a reviewer working through the third batch has as much
    right to know what was skipped as one working through the first.
    """
    grouped: dict[str, list[ReviewItem]] = {}
    for item in items:
        grouped.setdefault(item.kind, []).append(item)

    batches = []
    for kind in sorted(grouped):
        members = grouped[kind]
        for start in range(0, len(members), screenful):
            batches.append(ReviewBatch(
                kind=kind,
                items=members[start: start + screenful],
                considered_not_proposed=list(considered or []),
            ))
    return batches


def approve(item: ReviewItem, approver: str, note: str) -> WriteProposal:
    """Sign a proposal. Requires a name and a reason, and refuses without both.

    The reason is not bureaucracy. It is the only artefact that distinguishes
    a reviewer who read the diff from one who clicked, and it is what somebody
    reads six months later when they want to know what the approval meant.
    """
    if not approver.strip():
        raise GateError(
            "approval_without_identity",
            "an approval needs a named approver. A blank name is a checkbox, "
            "and a checkbox is not an approval.",
        )
    if not note.strip():
        raise GateError(
            "approval_without_reason",
            f"approving {item.proposal.proposal_id} requires a written reason. "
            "Rejection does not. The asymmetry is deliberate: the friction "
            "belongs on the action that writes to a laboratory record.",
        )
    if item.blocking:
        raise GateError(
            "approval_over_numeric_mismatch",
            f"{item.proposal.proposal_id} contradicts the design file on "
            f"{len(item.blocking)} value(s): "
            f"{'; '.join(f.stated for f in item.blocking)}. Edit the proposal "
            "or reject it. This is the chapter's failure, and it is the one "
            "case the gate does not leave to a reviewer's memory.",
        )
    return item.proposal.model_copy(update={
        "approved_by": approver.strip(),
        "approved_at": datetime.now(timezone.utc),
        "approval_note": note.strip(),
    })


def reject(item: ReviewItem, actor: str, note: str | None = None) -> Decision:
    """Say no. No explanation required, because requiring one buys approvals."""
    return Decision(proposal_id=item.proposal.proposal_id, action="reject",
                    actor=actor, note=note, at=datetime.now(timezone.utc))


def edit(item: ReviewItem, payload: dict, editor: str) -> WriteProposal:
    """Change the proposal and leave it unapproved.

    An edited proposal is a new proposal. It goes back through the cross-check
    and back to the gate, because a reviewer who fixes a concentration by hand
    has just introduced a number nothing has checked.
    """
    if not editor.strip():
        raise GateError("edit_without_identity", "an edit needs a named editor")
    return item.proposal.model_copy(update={
        "payload": payload,
        "proposal_id": f"{item.proposal.proposal_id}-edited",
        "approved_by": None,
        "approved_at": None,
        "approval_note": None,
    })


def gate_summary(batches: list[ReviewBatch]) -> dict[str, Any]:
    """What the gate is about to show, as structure rather than as prose."""
    items = [item for batch_ in batches for item in batch_.items]
    numeric = [finding for item in items for finding in item.numeric]
    return {
        "status": "READY",
        "code": "awaiting_review",
        "batches": len(batches),
        "items": len(items),
        "highlighted": sum(1 for i in items if i.escalation == "highlighted"),
        "routine": sum(1 for i in items if i.escalation == "routine"),
        "numeric": summarise(numeric),
        "considered_not_proposed": (
            len(batches[0].considered_not_proposed) if batches else 0
        ),
    }
