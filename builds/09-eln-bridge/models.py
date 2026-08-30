"""Stage two: the agent proposes, it does not write.

``WriteProposal`` is the whole argument of this build compressed into a class.
Two fields are absent and that absence is the design: there is no ``update``
and no ``delete`` in ``operation``, so the worst thing a confused agent can do
to a laboratory record is add to it. Clutter is recoverable. A silently
rewritten result is not, because nobody knows to go looking for it.

Two fields are present and start empty. ``approved_by`` and ``approved_at``
are unset until a person sets them, and ``notebook.py`` refuses to form a
request while either is missing. An approval with no named identity is not an
approval, it is a checkbox, and the difference matters on the morning somebody
asks who agreed to this.

``derived_from`` is the field people leave out. It names the records that
informed the proposal, so a reviewer looking at a diff can go and read what
the agent read. Without it a proposal is an assertion; with it the assertion
is checkable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WriteProposal(BaseModel):
    proposal_id: str
    target_system: str
    target_record: str | None          # None means create
    operation: Literal["create", "append"]   # note: no update, no delete
    payload: dict
    derived_from: list[str]            # record IDs that informed this
    model_id: str
    model_version: str
    run_id: str
    proposed_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_note: str | None = None

    @property
    def is_approved(self) -> bool:
        """Both fields, and a name with something in it.

        ``approved_by=""`` is the case this property exists for. It is what an
        automated approver writes when somebody wires one up, and it passes a
        truthiness check on the field being present.
        """
        return bool((self.approved_by or "").strip()) and self.approved_at is not None


class NotebookEntry(BaseModel):
    """What the notebook says came back, kept exactly as it answered.

    The ledger stores this rather than a summary of it. A response nobody
    kept is a write nobody can prove happened.
    """

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    record_id: str
    project: str
    record_type: str
    operation: Literal["create", "append"]
    body: str
    # Machine attribution, on every entry, not just the ones that went wrong.
    written_by_model: str
    written_by_model_version: str
    run_id: str
    approved_by: str
    written_at: datetime


class ConsideredNotProposed(BaseModel):
    """A record the agent read and decided against writing anything about.

    Chapter 6's principle, arriving again. An agent that reports only its
    actions lets a reviewer walk past everything it decided, and the decision
    not to act on the one record that mattered is invisible in a list of the
    four it did act on.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: str
    reason: str = Field(min_length=1)
