"""The manifest: everything a run needed, written down while it ran.

Nothing in this file is new, and that was the point of leaving it until the
tenth build. A provenance system bolted on at the end is always incomplete in
exactly the ways that matter, because the fields you forgot are the fields
nobody was recording, and no amount of care at the end recovers them. Every
fragment here already existed somewhere:

    step trace, model version, step count, stop reason   Build 01
    criteria file version, stamped on every verdict      Build 03
    approved column mapping with unit evidence           Build 05
    synergy model commitment, with its timestamp         Build 06
    structure record, box strategy, engine, seed         Build 08
    write proposals, approvals, approver identity        Build 09

They are collected by copying the record shapes rather than by importing them.
Each build stands alone, and a manifest that imported six builds would be a
manifest that only runs inside this repository.

``corpus_snapshot_id`` is the one field here that the printed listing does not
carry. The chapter's failure account ends by adding exactly this field, because
a replay that disagrees has to be able to say which version of the world it
operated on. It is a hash over the sorted input identifiers and their content
hashes, and a fetched response counts as an input: the endpoint and query are
the identifier and the response digest is the content. Leaving external
responses out of it would produce a corpus identifier that stayed constant
across precisely the drift it exists to describe.

``git_dirty`` is recorded rather than forbidden. A run from an uncommitted tree
is disclosed, not blocked. The commit hash alone does not identify the code
that ran, and a system that pretends otherwise is worse than one that admits
it, because it converts a known unknown into a false certainty.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from hashing import hash_text
from pydantic import BaseModel, ConfigDict, Field


class ModelUse(BaseModel):
    """One model, as it was configured. Not "we used Claude"."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str
    version: str
    temperature: float
    seed: int | None = None


class InputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    bytes: int
    retrieved_at: datetime


class ExternalCall(BaseModel):
    """A call out, with the answer hashed.

    This is the field that converts database drift from an invisible confound
    into a detectable event. Without it, a run that disagrees with its own
    replay is a mystery; with it, it is four lines in a difference report.
    """

    model_config = ConfigDict(extra="forbid")

    endpoint: str
    query: str
    response_sha256: str
    called_at: datetime

    @property
    def identifier(self) -> str:
        return f"{self.endpoint}?{self.query}"


class OutputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    bytes: int


class RunManifest(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["COMPLETE", "INCOMPLETE", "FAILED"]
    halt_reason: str | None

    # environment
    python_version: str
    lockfile_sha256: str
    git_commit: str
    git_dirty: bool                  # uncommitted changes present

    # models, one entry per distinct model used
    models: list[ModelUse]           # id, version, temperature, seed

    # inputs, addressed by content rather than by name
    inputs: list[InputRecord]        # path, sha256, bytes, retrieved_at
    external_calls: list[ExternalCall]   # endpoint, query, response_sha256

    # decisions carried from earlier chapters
    criteria_version: int | None
    mapping_ids: list[str]
    design_ids: list[str]
    approvals: list[str]

    # outputs
    outputs: list[OutputRecord]      # path, sha256
    trace_path: str
    trace_sha256: str

    # Not in the printed listing. The chapter's failure account ends by adding
    # exactly this field, so it is here with a note saying so rather than
    # quietly inside the block a reader is typing from the page.
    corpus_snapshot_id: str = ""

    model_config = ConfigDict(protected_namespaces=())

    def describe(self) -> str:
        """The sentence that belongs at the top of every difference report.

        Nothing is reproducible in the abstract. A run is reproducible against
        a stated corpus, at a stated commit, with stated versions, and a claim
        that omits any of the three is not a claim anybody can check.
        """
        versions = ", ".join(f"{use.id}@{use.version}" for use in self.models)
        tree = "a dirty tree" if self.git_dirty else "a clean tree"
        return (
            f"Run {self.run_id} is reproducible against corpus snapshot "
            f"{self.corpus_snapshot_id or 'UNRECORDED'}, at commit "
            f"{self.git_commit} from {tree}, with "
            f"{versions or 'no model recorded'}, on Python "
            f"{self.python_version}. Status {self.status}"
            + (f", halted because {self.halt_reason}." if self.halt_reason
               else ".")
        )

    @property
    def is_finished(self) -> bool:
        return self.status == "COMPLETE"

    def input_named(self, path: str) -> InputRecord | None:
        for record in self.inputs:
            if record.path == path:
                return record
        return None

    def output_named(self, path: str) -> OutputRecord | None:
        for record in self.outputs:
            if record.path == path:
                return record
        return None


class IncompleteRun(RuntimeError):
    """A consumer asked an unfinished run for its conclusions.

    Build 01's failure, still being guarded against nine builds later. A run
    that exhausted its step cap has partial work and no answer, and the
    dangerous thing is not the halt but the summary somebody writes from it.
    """

    def __init__(self, manifest: RunManifest) -> None:
        super().__init__(
            f"run {manifest.run_id} has status {manifest.status} and halted "
            f"because {manifest.halt_reason!r}. Its outputs are partial work, "
            "not results, and nothing downstream may treat them as finished."
        )
        self.code = "run_not_complete"
        self.run_id = manifest.run_id
        self.status = manifest.status
        self.halt_reason = manifest.halt_reason

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "code": self.code,
                "run_id": self.run_id, "halt_reason": self.halt_reason,
                "answer": None}


def corpus_snapshot(inputs: list[InputRecord],
                    external_calls: list[ExternalCall]) -> str:
    """Which version of the world a run operated on, as one identifier.

    Sorted, so the order things were read in does not change the answer. A
    fetched response is an input: the endpoint and query name it, the response
    digest is its content. That is the whole reason this field earns its place,
    because the drift it has to describe is almost always on the other side of
    a network call rather than in a file on your disk.
    """
    lines = sorted(
        [f"file:{record.path}={record.sha256}" for record in inputs]
        + [f"call:{call.identifier}={call.response_sha256}"
           for call in external_calls]
    )
    return hash_text("\n".join(lines))


def load_manifest(path: str | Path) -> RunManifest:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunManifest(**body)


def require_complete(manifest: RunManifest) -> RunManifest:
    """The downstream guard. Raises rather than returning a partial answer."""
    if not manifest.is_finished:
        raise IncompleteRun(manifest)
    return manifest


class ManifestBuilder(BaseModel):
    """Collect fragments while a run happens, rather than reconstructing after.

    The order of the fields is the order they become knowable. Nothing here
    can be filled in afterwards from memory, which is the point: a manifest
    assembled at the end is a manifest of what somebody remembered.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    run_id: str
    started_at: datetime
    python_version: str
    lockfile_sha256: str
    git_commit: str
    git_dirty: bool
    models: list[ModelUse] = Field(default_factory=list)
    inputs: list[InputRecord] = Field(default_factory=list)
    external_calls: list[ExternalCall] = Field(default_factory=list)
    criteria_version: int | None = None
    mapping_ids: list[str] = Field(default_factory=list)
    design_ids: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    outputs: list[OutputRecord] = Field(default_factory=list)

    def finish(self, status: str, finished_at: datetime, trace_path: str,
               trace_sha256: str, halt_reason: str | None = None
               ) -> RunManifest:
        return RunManifest(
            run_id=self.run_id,
            started_at=self.started_at,
            finished_at=finished_at,
            status=status,
            halt_reason=halt_reason,
            python_version=self.python_version,
            lockfile_sha256=self.lockfile_sha256,
            git_commit=self.git_commit,
            git_dirty=self.git_dirty,
            models=self.models,
            inputs=self.inputs,
            external_calls=self.external_calls,
            criteria_version=self.criteria_version,
            mapping_ids=self.mapping_ids,
            design_ids=self.design_ids,
            approvals=self.approvals,
            outputs=self.outputs,
            trace_path=trace_path,
            trace_sha256=trace_sha256,
            corpus_snapshot_id=corpus_snapshot(self.inputs,
                                               self.external_calls),
        )
