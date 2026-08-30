"""The notebook interface, and the two capabilities it deliberately lacks.

``NotebookClient`` admits ``create`` and ``append`` and nothing else. There is
no update method and no delete method, not as a policy the code checks but as
an absence: a capability that does not exist cannot be invoked by a confused
agent, by a determined one, or by a future maintainer in a hurry. It converts
the worst realistic outcome of this build from data loss into clutter, and
clutter is a thing you can clean up on a Tuesday.

That absence is load-bearing enough to be asserted. ``destructive_members``
walks a class and returns anything that reads as a rewrite or a removal, and
the gate calls it on the protocol and on both implementations.

Two implementations. ``StubNotebook`` is backed by the committed fixtures and
is what the tests run. ``HttpNotebook`` is the shape a real connector takes
and is what a reader adapts; nothing in the gate touches it, because a test
that needs a server is a test that fails on a train.

Every write goes through ``authorise``, which is where approval, attribution
and scope are enforced. It runs before a request is formed, so an unapproved
proposal never becomes a call that a server declines and an audit log then
records as an attempt.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx
from models import NotebookEntry, WriteProposal
from scope import Scope, ScopeError
from untrusted import RetrievedContent

# Anything whose name reads as a rewrite or a removal. The list is generous on
# purpose: this is asserted against, and a method called patch_record that
# slipped past a narrow list would be exactly the method worth catching.
DESTRUCTIVE_NAMES = (
    "update", "delete", "patch", "put", "remove", "overwrite", "replace",
    "destroy", "truncate", "drop", "purge", "edit", "modify", "rewrite",
    "amend", "revise", "set_body", "clear",
)


class NotebookError(RuntimeError):
    """A write was refused, or the notebook could not answer.

    Carries a code rather than a sentence. ``as_dict`` is what goes back into
    a model's context on the paths that feed one, because prose describing a
    failure is something a model will try to act on.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


def destructive_members(target: type | object) -> list[str]:
    """Public members of `target` whose names read as a rewrite or a removal.

    Used by the gate to assert the interface rather than the policy. A build
    that grew an update method would fail here before it failed anywhere that
    mattered.
    """
    found = []
    for name in dir(target):
        if name.startswith("_"):
            continue
        lowered = name.lower()
        if any(word in lowered for word in DESTRUCTIVE_NAMES):
            found.append(name)
    return sorted(found)


@runtime_checkable
class NotebookClient(Protocol):
    """Read freely, write only through the gate. Four methods, no more.

    The protocol is the specification of what a connector to a laboratory
    notebook is allowed to be in this build. Adding a fifth method that
    rewrites a record is a change somebody has to make deliberately, in this
    file, past a test that says not to.
    """

    scope: Scope

    def get(self, record_id: str) -> RetrievedContent: ...

    def list_records(self, record_type: str | None = None) -> list[str]: ...

    def create(self, proposal: WriteProposal) -> NotebookEntry: ...

    def append(self, proposal: WriteProposal) -> NotebookEntry: ...


def authorise(proposal: WriteProposal, expected: str, scope: Scope,
              project: str, record_type: str) -> None:
    """Every reason to refuse a write, in one place, before a request exists.

    Scope is checked first because it is the question of whether this client
    should be forming a request about this record at all. Approval is checked
    second, and it is checked here rather than at the gate because the gate is
    a user interface and this is the boundary. A second gate somebody forgets
    to call is not a gate.
    """
    scope.check(project, record_type)

    if proposal.operation != expected:
        raise NotebookError(
            "operation_mismatch",
            f"a {expected} was requested and the proposal says "
            f"{proposal.operation!r}",
        )

    if not proposal.is_approved:
        raise NotebookError(
            "not_approved",
            f"proposal {proposal.proposal_id} has approved_by="
            f"{proposal.approved_by!r} and approved_at="
            f"{proposal.approved_at!r}. Both must be set, and a name that is "
            "blank or whitespace is not a name. An approval without an "
            "identity is not an approval.",
        )

    for field in ("model_id", "model_version", "run_id"):
        if not str(getattr(proposal, field) or "").strip():
            raise NotebookError(
                "attribution_missing",
                f"proposal {proposal.proposal_id} has no {field}. Every entry "
                "this build writes carries machine attribution, because an "
                "entry nobody can attribute is an entry somebody will assume "
                "a person wrote.",
            )


class StubNotebook:
    """A notebook backed by the committed fixtures, with an in-memory store.

    Reads come from ``fixtures/notebook``. Writes go into ``self.entries`` and
    are never written back to the fixture files, so the corpus a test starts
    from is the corpus the next test starts from.

    ``self.requests`` counts requests that were actually formed. It is what
    the gate asserts on: a refusal must leave it untouched, because a refusal
    that still formed the request has only moved the problem to the server.
    """

    def __init__(self, corpus: str | Path, scope: Scope) -> None:
        self.corpus = Path(corpus)
        self.scope = scope
        self.entries: list[NotebookEntry] = []
        self.requests: list[dict[str, Any]] = []
        self._records: dict[str, dict[str, Any]] = {}
        # A file may hold one record or a list of them. The twenty ordinary
        # records travel together because they are bulk corpus; each injection
        # fixture gets its own file because each one is an argument.
        for path in sorted(self.corpus.glob("*.json")):
            if path.name.endswith(".expected.json"):
                continue
            body = json.loads(path.read_text(encoding="utf-8"))
            for record in (body if isinstance(body, list) else [body]):
                self._records[record["record_id"]] = record

    def _raw(self, record_id: str) -> dict[str, Any]:
        record = self._records.get(record_id)
        if record is None:
            raise NotebookError(
                "record_not_found", f"no record {record_id!r} in the corpus"
            )
        return record

    def get(self, record_id: str) -> RetrievedContent:
        """Read one record, scope-checked, wrapped as untrusted."""
        record = self._raw(record_id)
        self.scope.check(record["project"], record["record_type"])
        self.requests.append({"verb": "GET", "record_id": record_id})
        # The title travels inside the body on purpose. A directive placed in
        # a title is invisible to anything that scans only the body, and that
        # is the shape of one of the six injection fixtures.
        title = record["title"]
        return RetrievedContent(
            source_system="stub-eln",
            record_id=record["record_id"],
            author=record["author"],
            retrieved_at=datetime.fromisoformat(record["created_at"]),
            body=f"{title}\n\n{record['body']}",
        )

    def record_type_of(self, record_id: str) -> str:
        return self._raw(record_id)["record_type"]

    def project_of(self, record_id: str) -> str:
        return self._raw(record_id)["project"]

    def list_records(self, record_type: str | None = None) -> list[str]:
        """Identifiers in scope, and only those."""
        out = []
        for record_id, record in sorted(self._records.items()):
            if record["project"] != self.scope.project:
                continue
            if record["record_type"] not in self.scope.record_types:
                continue
            if record_type is not None and record["record_type"] != record_type:
                continue
            out.append(record_id)
        return out

    def _write(self, proposal: WriteProposal, operation: str, record_id: str,
               project: str, record_type: str) -> NotebookEntry:
        authorise(proposal, operation, self.scope, project, record_type)
        self.requests.append({"verb": "POST", "record_id": record_id,
                              "operation": operation})
        entry = NotebookEntry(
            entry_id=f"ENT-{uuid.uuid4().hex[:10]}",
            record_id=record_id,
            project=project,
            record_type=record_type,
            operation=proposal.operation,
            body=str(proposal.payload.get("body", "")),
            written_by_model=proposal.model_id,
            written_by_model_version=proposal.model_version,
            run_id=proposal.run_id,
            approved_by=str(proposal.approved_by),
            written_at=datetime.now(timezone.utc),
        )
        self.entries.append(entry)
        if operation == "create":
            self._records[record_id] = {
                "record_id": record_id,
                "project": project,
                "record_type": record_type,
                "title": str(proposal.payload.get("title", "")),
                "author": f"{proposal.model_id} for {proposal.approved_by}",
                "created_at": entry.written_at.isoformat(),
                "body": entry.body,
            }
        else:
            self._records[record_id]["body"] += "\n\n" + entry.body
        return entry

    def create(self, proposal: WriteProposal) -> NotebookEntry:
        project = str(proposal.payload.get("project", ""))
        record_type = str(proposal.payload.get("record_type", ""))
        record_id = f"ELN-{uuid.uuid4().hex[:8].upper()}"
        return self._write(proposal, "create", record_id, project, record_type)

    def append(self, proposal: WriteProposal) -> NotebookEntry:
        if proposal.target_record is None:
            raise NotebookError(
                "no_target_record", "an append needs a record to append to"
            )
        # Read the record first, so the scope check uses the notebook's own
        # answer for project and record type rather than the proposal's claim
        # about them. A proposal that declares its own scope can widen it.
        record = self._raw(proposal.target_record)
        return self._write(proposal, "append", record["record_id"],
                           record["project"], record["record_type"])


class HttpNotebook:
    """The shape a real connector takes. Nothing in the gate calls this.

    It is here because the stub is what runs and this is what a reader adapts,
    and because the interface argument is only convincing if it survives
    contact with an implementation that could have had a DELETE in it. There
    is no delete here either, and the base URL plus the scope is the whole
    configuration surface.
    """

    def __init__(self, base_url: str, token: str, scope: Scope,
                 client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.scope = scope
        self._token = token
        self._client = client

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30.0,
            )
        return self._client

    def get(self, record_id: str) -> RetrievedContent:
        response = self._http().get(f"{self.base_url}/records/{record_id}")
        response.raise_for_status()
        body = response.json()
        self.scope.check(body["project"], body["record_type"])
        return RetrievedContent(
            source_system=self.base_url,
            record_id=body["record_id"],
            author=body["author"],
            retrieved_at=datetime.fromisoformat(body["created_at"]),
            body=f"{body['title']}\n\n{body['body']}",
        )

    def list_records(self, record_type: str | None = None) -> list[str]:
        params = {"project": self.scope.project}
        if record_type is not None:
            self.scope.check_record_type(record_type)
            params["record_type"] = record_type
        response = self._http().get(f"{self.base_url}/records", params=params)
        response.raise_for_status()
        return [item["record_id"] for item in response.json()["records"]]

    def _post(self, proposal: WriteProposal, operation: str, url: str,
              project: str, record_type: str) -> NotebookEntry:
        authorise(proposal, operation, self.scope, project, record_type)
        response = self._http().post(url, json={
            "payload": proposal.payload,
            "operation": proposal.operation,
            "attribution": {
                "model_id": proposal.model_id,
                "model_version": proposal.model_version,
                "run_id": proposal.run_id,
                "approved_by": proposal.approved_by,
                "proposal_id": proposal.proposal_id,
            },
        })
        response.raise_for_status()
        body = response.json()
        return NotebookEntry(
            entry_id=body["entry_id"],
            record_id=body["record_id"],
            project=project,
            record_type=record_type,
            operation=proposal.operation,
            body=str(proposal.payload.get("body", "")),
            written_by_model=proposal.model_id,
            written_by_model_version=proposal.model_version,
            run_id=proposal.run_id,
            approved_by=str(proposal.approved_by),
            written_at=datetime.fromisoformat(body["written_at"]),
        )

    def create(self, proposal: WriteProposal) -> NotebookEntry:
        return self._post(
            proposal, "create", f"{self.base_url}/records",
            str(proposal.payload.get("project", "")),
            str(proposal.payload.get("record_type", "")),
        )

    def append(self, proposal: WriteProposal) -> NotebookEntry:
        if proposal.target_record is None:
            raise NotebookError(
                "no_target_record", "an append needs a record to append to"
            )
        response = self._http().get(
            f"{self.base_url}/records/{proposal.target_record}"
        )
        response.raise_for_status()
        current = response.json()
        return self._post(
            proposal, "append",
            f"{self.base_url}/records/{proposal.target_record}/entries",
            current["project"], current["record_type"],
        )


__all__ = [
    "DESTRUCTIVE_NAMES",
    "HttpNotebook",
    "NotebookClient",
    "NotebookError",
    "ScopeError",
    "StubNotebook",
    "authorise",
    "destructive_members",
]
