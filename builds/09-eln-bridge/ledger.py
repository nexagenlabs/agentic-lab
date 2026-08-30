"""The append-only local ledger, which the notebook cannot overwrite.

The notebook has an audit trail. It is the vendor's audit trail, it lives in
the vendor's database, and its retention is the vendor's policy. All three of
those can change without anybody asking you, and when you migrate systems the
new vendor imports the records and not the trail. Your evidence of what your
agent proposed, what a person approved and what came back should not depend on
somebody else's database still existing in that form in three years.

So every approved proposal is written twice. Once into the notebook, which is
the record of the science, and once here, which is the record of the machine.
The two are reconciled by ``test_ledger_matches_notebook``: an entry in the
notebook with no ledger line is the failure this chapter exists to prevent,
because it is an agent write that nothing outside the vendor can account for.

Append-only is the mechanism and the interface. The file is opened in append
mode and never in write mode, and this class has no method that removes or
rewrites a line. It is the same argument as the missing delete on the notebook
client: the way to be sure a capability is not misused is not to have it.

This is the file Build 10 builds its manifest from.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gate import Decision
from models import NotebookEntry, WriteProposal


class Ledger:
    """One JSONL file for one run, opened in append mode and nothing else."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, kind: str, body: dict[str, Any]) -> None:
        line = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind,
                **body}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, default=str) + "\n")

    def proposed(self, proposal: WriteProposal) -> None:
        """Written when the agent proposes, before anybody has looked at it.

        Proposals that are rejected are in here too. A gate that only records
        what it let through cannot tell you what it stopped, and what it
        stopped is the more interesting half.
        """
        self._append("proposed", {"proposal": proposal.model_dump(mode="json")})

    def decided(self, decision: Decision) -> None:
        self._append("decided", {"decision": decision.model_dump(mode="json")})

    def approved(self, proposal: WriteProposal) -> None:
        self._append("approved", {"proposal": proposal.model_dump(mode="json")})

    def written(self, proposal_id: str, entry: NotebookEntry) -> None:
        """The notebook's own answer, kept verbatim rather than summarised."""
        self._append("written", {"proposal_id": proposal_id,
                                 "entry": entry.model_dump(mode="json")})

    def flagged(self, code: str, body: dict[str, Any]) -> None:
        self._append("flagged", {"code": code, **body})

    def lines(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [line for line in self.lines() if line["kind"] == kind]

    def approved_proposal_ids(self) -> list[str]:
        return [line["proposal"]["proposal_id"] for line in self.of_kind("approved")]

    def written_entry_ids(self) -> list[str]:
        return [line["entry"]["entry_id"] for line in self.of_kind("written")]

    def reconcile(self, entries: list[NotebookEntry]) -> dict[str, Any]:
        """Does the ledger account for every entry the notebook holds?

        Returns structure rather than a verdict sentence, and names the
        entries on both sides that have no partner. An entry the ledger cannot
        account for is the one worth chasing, and it is listed first.
        """
        written = {line["entry"]["entry_id"]: line["proposal_id"]
                   for line in self.of_kind("written")}
        approved = set(self.approved_proposal_ids())
        in_notebook = {entry.entry_id for entry in entries}

        unaccounted = sorted(in_notebook - set(written))
        unapproved = sorted(
            entry_id for entry_id, proposal_id in written.items()
            if proposal_id not in approved
        )
        orphaned = sorted(set(written) - in_notebook)
        return {
            "status": "MATCHED" if not (unaccounted or unapproved or orphaned)
            else "MISMATCHED",
            "code": "ledger_matches_notebook" if not (
                unaccounted or unapproved or orphaned) else "ledger_mismatch",
            "notebook_entries": len(in_notebook),
            "ledger_writes": len(written),
            "approved_proposals": len(approved),
            "entries_with_no_ledger_record": unaccounted,
            "entries_with_no_approved_proposal": unapproved,
            "ledger_records_with_no_entry": orphaned,
        }
