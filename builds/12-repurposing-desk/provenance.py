"""One manifest for the whole run, and the trace that makes replay possible.

Build 10's record shapes, copied rather than imported, because each build
stands alone. What is new here is that a single manifest spans nine stages
rather than one, which is the only way the question "did this shortlist follow
from these inputs" can be asked of the desk as a whole.

## Why the manifest is also the run context

The printed listing is ``run_desk(question, manifest)`` and nothing else. There
is no client parameter, no approvals directory and no accounting object. So the
manifest carries them: it is configuration going in and provenance coming out.

That is forced by the signature rather than chosen, and on reflection it is
the right shape anyway. The things ``run_desk`` needs from its environment are
exactly the things that have to be recorded about the run: which models, at
which versions, whose approvals, over which inputs. A parameter list that
carried them separately would be a list of things somebody could pass without
recording.

## The trace stores completions

``model_call`` events carry the raw completion text. Audit replay reconstructs
the run by serving those completions back in order, so it needs no model, no
key and no network, and it keeps working after the version that produced them
has been retired. Storing conclusions instead would make the replay a check
that a summary was copied correctly.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CHUNK = 65536


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def hash_json(payload: Any) -> str:
    return hash_text(canonical_json(payload))


class ModelUse(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str
    version: str
    tier: str
    temperature: float = 0.0


class InputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    bytes: int


class OutputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    bytes: int


class ExternalCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    query: str
    response_sha256: str

    @property
    def identifier(self) -> str:
        return f"{self.endpoint}?{self.query}"


class Approval(BaseModel):
    """Build 09's shape: an approval with no named identity is not one."""

    model_config = ConfigDict(extra="forbid")

    checkpoint: str
    approved_by: str = Field(min_length=1)
    approved_at: datetime
    note: str = Field(min_length=1)
    reviewed_sha256: str

    @property
    def is_approval(self) -> bool:
        return bool(self.approved_by.strip()) and bool(self.note.strip())


class StageCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    level: str
    seconds: float
    tokens: dict[str, int] = Field(default_factory=dict)
    model_calls: int = 0
    max_calls_per_item: int = 0
    human_minutes: int = 0
    human_note: str = ""

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens.values())


def git_state(root: Path) -> tuple[str, bool]:
    """The commit and whether the tree was dirty. Recorded, never blocking.

    Falls back to a recorded absence rather than raising. A run from a
    directory that is not a checkout is a run whose code cannot be identified,
    and saying so is better than pretending.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, timeout=10, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True,
            text=True, timeout=10, check=True,
        ).stdout.strip()
        return commit, bool(status)
    except (OSError, subprocess.SubprocessError):
        return "UNRECORDED", True


class Trace:
    """Append-only JSONL, one event per line, with the completions in it."""

    def __init__(self, path: Path, clock: Any = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def write(self, event: str, **fields: Any) -> None:
        self._n += 1
        record = {"seq": self._n, "ts": self._clock(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, default=str, sort_keys=True) + "\n")

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


def completions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The raw text the model returned, in order, with the stage that asked."""
    return [{"stage": event["stage"], "text": event["text"]}
            for event in events if event["event"] == "model_call"]


class RunManifest:
    """Configuration in, provenance out. One of these spans the whole desk."""

    def __init__(self, run_id: str, root: Path, client: Any,
                 approvals_dir: Path, workspace: Path,
                 clock: Any = None) -> None:
        self.run_id = run_id
        self.root = Path(root)
        self.client = client
        self.approvals_dir = Path(approvals_dir)
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.started_at = datetime.now(timezone.utc)
        self.trace = Trace(self.workspace / f"{run_id}.jsonl", clock=clock)

        commit, dirty = git_state(self.root)
        self.git_commit = commit
        self.git_dirty = dirty
        self.python_version = platform.python_version()

        self.models: list[ModelUse] = []
        self.inputs: list[InputRecord] = []
        self.outputs: list[OutputRecord] = []
        self.external_calls: list[ExternalCall] = []
        self.approvals: list[Approval] = []
        self.stages: list[StageCost] = []
        self.criteria_version: int | None = None
        self.mapping_ids: list[str] = []
        self.design_ids: list[str] = []
        self.status = "RUNNING"
        self.halt_reason: str | None = None
        # Set by desk.prepare. The printed spine passes only the question and
        # the manifest, so a stage needing the question reads it from here.
        self.question: Any = None
        self.evidence: dict[str, list[str]] = {}

    # -- collection ---------------------------------------------------------

    def record_input(self, path: Path) -> InputRecord:
        path = Path(path)
        relative = str(path.relative_to(self.root)).replace("\\", "/")
        record = InputRecord(path=relative, sha256=hash_file(path),
                             bytes=path.stat().st_size)
        if not any(existing.path == record.path for existing in self.inputs):
            self.inputs.append(record)
        return record

    def record_output(self, name: str, payload: Any) -> OutputRecord:
        path = self.workspace / name
        text = canonical_json(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        record = OutputRecord(path=name, sha256=hash_text(text),
                              bytes=len(text.encode("utf-8")))
        self.outputs = [o for o in self.outputs if o.path != name] + [record]
        return record

    def record_model(self, use: ModelUse) -> None:
        if not any(existing.id == use.id and existing.version == use.version
                   for existing in self.models):
            self.models.append(use)

    def record_stage(self, cost: StageCost) -> None:
        self.stages.append(cost)

    def record_approval(self, approval: Approval) -> None:
        self.approvals.append(approval)

    def output_named(self, name: str) -> OutputRecord | None:
        for record in self.outputs:
            if record.path == name:
                return record
        return None

    # -- provenance ---------------------------------------------------------

    def corpus_snapshot_id(self) -> str:
        """Which version of the world, over inputs and fetched responses."""
        lines = sorted(
            [f"file:{record.path}={record.sha256}" for record in self.inputs]
            + [f"call:{call.identifier}={call.response_sha256}"
               for call in self.external_calls]
        )
        return hash_text("\n".join(lines))

    def describe(self) -> str:
        versions = ", ".join(f"{use.id}@{use.version}" for use in self.models)
        tree = "a dirty tree" if self.git_dirty else "a clean tree"
        return (
            f"Desk run {self.run_id} is reproducible against corpus snapshot "
            f"{self.corpus_snapshot_id()}, at commit {self.git_commit} from "
            f"{tree}, with {versions or 'no model recorded'}, on Python "
            f"{self.python_version}. Status {self.status}."
        )

    def finalise(self) -> dict[str, Any]:
        """The manifest as a record. Written to disk and returned."""
        self.status = "COMPLETE" if self.halt_reason is None else "INCOMPLETE"
        trace_sha = (hash_file(self.trace.path) if self.trace.path.exists()
                     else "")
        body = {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": self.status,
            "halt_reason": self.halt_reason,
            "python_version": self.python_version,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "models": [use.model_dump(mode="json") for use in self.models],
            "inputs": [record.model_dump() for record in self.inputs],
            "external_calls": [call.model_dump()
                               for call in self.external_calls],
            "criteria_version": self.criteria_version,
            "mapping_ids": self.mapping_ids,
            "design_ids": self.design_ids,
            "approvals": [a.model_dump(mode="json") for a in self.approvals],
            "outputs": [record.model_dump() for record in self.outputs],
            "stages": [stage.model_dump() for stage in self.stages],
            "trace_path": self.trace.path.name,
            "trace_sha256": trace_sha,
            "corpus_snapshot_id": self.corpus_snapshot_id(),
            "describe": self.describe(),
        }
        (self.workspace / "manifest.json").write_text(
            canonical_json(body), encoding="utf-8", newline="\n"
        )
        return body
