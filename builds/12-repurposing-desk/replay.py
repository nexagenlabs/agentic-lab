"""Audit replay of a whole desk run. No model, no network, no key.

The trick, if it is one, is that there is no replay-specific code inside
``run_desk``. Every model call in the desk goes through ``stages.ask``, which
calls ``manifest.client.complete``. Audit replay builds a manifest whose client
is a ``ReplayClient`` over the recorded completions and runs the same spine.

That has a property worth more than the offline guarantee. The replay follows
the same control flow the original run followed, and ``ReplayClient`` refuses
if the stage asking for completion *n* is not the stage that produced it. So a
replay that reproduces the outputs has reproduced the path as well, and a
replay that took a different route through the pipeline fails loudly instead of
arriving at the same answer by another road.

Input drift halts it, and the file that changed is named. A manifest that
notices a changed input and carries on is decorative.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import desk
from provenance import (
    RunManifest,
    canonical_json,
    completions,
    hash_file,
    hash_text,
)
from stub_client import ReplayClient


class ReplayHalted(RuntimeError):
    """A replay stopped before comparing outputs, and says which file."""

    def __init__(self, code: str, path: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.path = path
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "HALTED", "code": self.code, "path": self.path,
                "detail": self.detail}


def verify_inputs(recorded: dict[str, Any], root: Path) -> None:
    """Halt, naming the file, the moment an input no longer hashes the same."""
    for record in recorded["inputs"]:
        path = Path(root) / record["path"]
        if not path.exists():
            raise ReplayHalted("input_missing", record["path"],
                               f"{record['path']} is in the manifest and is "
                               "not on disk")
        actual = hash_file(path)
        if actual != record["sha256"]:
            raise ReplayHalted(
                "input_changed", record["path"],
                f"{record['path']} no longer matches the manifest. Recorded "
                f"{record['sha256'][:16]}, found {actual[:16]}.",
            )


def audit_replay(recorded: dict[str, Any], trace_path: Path, root: Path,
                 approvals_dir: Path, workspace: Path) -> dict[str, Any]:
    """Rebuild the desk's outputs from the stored trace, offline."""
    verify_inputs(recorded, root)

    trace_path = Path(trace_path)
    if not trace_path.exists():
        raise ReplayHalted("trace_missing", str(trace_path),
                           "there is no trace to replay from")
    if hash_file(trace_path) != recorded["trace_sha256"]:
        raise ReplayHalted(
            "trace_changed", trace_path.name,
            "the trace no longer matches the manifest, so it is not evidence "
            "of this run any more",
        )

    events = [json.loads(line) for line
              in trace_path.read_text(encoding="utf-8").splitlines() if line]
    client = ReplayClient(completions(events))

    manifest = RunManifest(
        run_id=f"{recorded['run_id']}-replay", root=root, client=client,
        approvals_dir=approvals_dir, workspace=workspace,
    )
    question = desk.load_question()
    shortlist = desk.run(question, manifest)

    matched, mismatched = [], []
    for record in recorded["outputs"]:
        produced = manifest.output_named(record["path"])
        if produced is None:
            mismatched.append({"path": record["path"],
                               "expected": record["sha256"],
                               "actual": "not produced"})
        elif produced.sha256 == record["sha256"]:
            matched.append(record["path"])
        else:
            mismatched.append({"path": record["path"],
                               "expected": record["sha256"],
                               "actual": produced.sha256})

    return {
        "status": "REPRODUCED" if not mismatched else "DIVERGED",
        "code": "outputs_match" if not mismatched else "outputs_differ",
        "run_id": recorded["run_id"],
        "matched": matched,
        "mismatched": mismatched,
        "completions_replayed": client.position,
        "model_calls_made": 0,
        "shortlist": shortlist.compounds(),
    }


def output_digest(payload: Any) -> str:
    """The digest an output would have, for a caller comparing by content."""
    return hash_text(canonical_json(payload))
