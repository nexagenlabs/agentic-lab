"""The three checkpoints, which are the spine of the desk.

Each one blocks. Each one writes a named approval into the manifest. Each one
sits immediately before an irreversible narrowing:

    screening   before the corpus is cut to what will be read in full. What is
                excluded here is never seen again.
    targets     before compute is spent. Docking the wrong target is a day and
                a shortlist that looks fine.
    shortlist   before anything reaches a bench. This is the expensive one and
                the chapter says so: ninety minutes of somebody looking at
                three compounds, which nothing automates.

Approval machinery is Build 09's, copied. A named identity and a written
reason, both required, because an approval with neither is a checkbox.

## The approval is bound to what was approved

``reviewed_sha256`` is the hash of the thing the reviewer saw. If a stage
upstream changes and the payload is no longer the payload that was signed, the
checkpoint refuses with ``approval_is_for_different_content`` rather than
letting a stale approval carry a new artefact through.

That is stricter than most systems and it is the point of writing it down. An
approval that survives a change to the thing it approved is not a record of
anybody's judgement, it is a token that accumulated authority by sitting in a
directory. The cost is that the committed approvals have to be regenerated
whenever a stage changes, which is what ``fixtures/make_checkpoints.py`` is
for, and the generator is committed alongside them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provenance import Approval, RunManifest, hash_json

# The three, in order, with the human time each is expected to take. These are
# declared rather than measured: they are markers saying attention is required
# here, and the accounting labels them as declared so nobody reads them as an
# observation.
CHECKPOINTS = {
    "screening": {
        "position": 1,
        "narrowing": "the corpus is cut to what will be read in full",
        "declared_minutes": 45,
    },
    "targets": {
        "position": 2,
        "narrowing": "compute is committed to a target and a box",
        "declared_minutes": 45,
    },
    "shortlist": {
        "position": 3,
        "narrowing": "a candidate goes to a bench",
        "declared_minutes": 90,
    },
}


class CheckpointBlocked(RuntimeError):
    """The run stopped at a checkpoint, and nothing downstream ran.

    Raised rather than returned. A checkpoint that returned a status would be
    a checkpoint a caller could ignore, and the whole property being defended
    is that the next stage does not execute.
    """

    def __init__(self, checkpoint: str, code: str, detail: str) -> None:
        super().__init__(f"{checkpoint} blocked ({code}): {detail}")
        self.checkpoint = checkpoint
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "BLOCKED", "code": self.code,
                "checkpoint": self.checkpoint, "detail": self.detail}


def approval_path(name: str, directory: Path) -> Path:
    return Path(directory) / f"{name}.json"


def load_approval(name: str, directory: Path) -> Approval:
    path = approval_path(name, directory)
    if not path.exists():
        raise CheckpointBlocked(
            name, "no_approval_recorded",
            f"there is no approval at {path}. Nothing downstream of this "
            "checkpoint runs until a person signs it.",
        )
    body = json.loads(path.read_text(encoding="utf-8"))
    return Approval(**body)


def checkpoint(name: str, payload: Any, manifest: RunManifest) -> Approval:
    """Block until a recorded approval covers exactly this payload."""
    if name not in CHECKPOINTS:
        raise CheckpointBlocked(name, "unknown_checkpoint",
                                f"{name!r} is not one of {sorted(CHECKPOINTS)}")

    digest = hash_json(_reviewable(payload))
    manifest.trace.write("checkpoint_reached", checkpoint=name,
                         reviewed_sha256=digest)

    approval = load_approval(name, manifest.approvals_dir)

    if not approval.is_approval:
        raise CheckpointBlocked(
            name, "approval_without_identity",
            "an approval needs a named approver and a written reason. Both "
            "are missing or blank, which is a checkbox rather than a "
            "judgement.",
        )
    if approval.checkpoint != name:
        raise CheckpointBlocked(
            name, "approval_for_another_checkpoint",
            f"the approval on file is for {approval.checkpoint!r}",
        )
    if approval.reviewed_sha256 != digest:
        raise CheckpointBlocked(
            name, "approval_is_for_different_content",
            f"the approval was signed over {approval.reviewed_sha256[:16]} "
            f"and this run produced {digest[:16]}. Something upstream changed "
            "after the approval was given, so the approval is not a record of "
            "anybody having looked at this.",
        )

    manifest.record_approval(approval)
    manifest.trace.write("checkpoint_approved", checkpoint=name,
                         approved_by=approval.approved_by)
    return approval


def _reviewable(payload: Any) -> Any:
    """What the reviewer is shown, which is what gets hashed.

    Pydantic models go through ``model_dump`` so that the digest is over the
    content rather than over an object address, and lists of them likewise.
    """
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    if isinstance(payload, list):
        return [_reviewable(item) for item in payload]
    return payload


def record_approval_for(name: str, payload: Any, approver: str, note: str,
                        directory: Path,
                        when: datetime | None = None) -> Approval:
    """Write an approval. Used by the fixture generator, never by the desk.

    The desk cannot approve anything. This function exists in a module the
    desk imports so that a reader can see there is exactly one way approvals
    come into being and that ``run_desk`` does not call it.
    """
    approval = Approval(
        checkpoint=name,
        approved_by=approver,
        approved_at=when or datetime.now(timezone.utc),
        note=note,
        reviewed_sha256=hash_json(_reviewable(payload)),
    )
    path = approval_path(name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(approval.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8", newline="\n",
    )
    return approval
