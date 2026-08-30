"""Two kinds of replay, and both are required.

They answer different questions and neither answer substitutes for the other.
Building only one is the mistake this module exists to prevent.

``verify_replay`` re-executes the pipeline. It needs the model, and the same
version of it, and it proves that **the result still follows from the inputs
today**. It is the replay that catches a model whose behaviour has moved under
you, and it stops working the day the vendor retires the version you ran.

``audit_replay`` reconstructs the run from the stored trace. It calls no model
and touches no network, and it proves that **the result followed from the
inputs then**. It survives model deprecation indefinitely, which is the only
property that matters when the question arrives four years later from somebody
who was not there.

Audit replay works only because the trace stored the completions rather than
the conclusions. If it ever starts reading a field this build wrote as a
conclusion, it has stopped proving anything about the run and started proving
that a summary was copied correctly.

Input drift halts both. A manifest that notices a changed input and carries on
is a manifest that is decorative, and the point of recording a digest is to
refuse when it stops matching.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from difference import difference_report
from hashing import hash_file, hash_json, hash_text
from models import RunManifest, load_manifest
from pipeline import outputs_from_completions, screen
from pydantic import BaseModel, ConfigDict, Field
from tracing import completions, external_responses, read_trace


class ReplayResult(BaseModel):
    """What a replay found, as structure rather than as prose."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    status: str
    code: str
    run_id: str
    outputs_checked: int = 0
    matched: list[str] = Field(default_factory=list)
    mismatched: list[dict[str, str]] = Field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "REPRODUCED"

    def render(self) -> str:
        head = f"{self.kind}: {self.status} ({self.code})"
        if not self.mismatched:
            return f"{head}\n  {self.outputs_checked} output(s) matched"
        lines = [head]
        for entry in self.mismatched:
            lines.append(f"  ! {entry['path']}")
            lines.append(f"      recorded {entry['expected']}")
            lines.append(f"      replayed {entry['actual']}")
        return "\n".join(lines)


def verify_inputs(manifest: RunManifest, root: str | Path) -> None:
    """Halt, naming the file, the moment an input no longer hashes the same.

    Named rather than counted. "An input changed" sends somebody through
    fourteen files; "inputs/corpus.json changed" sends them to one.
    """
    root = Path(root)
    for record in manifest.inputs:
        path = root / record.path
        if not path.exists():
            raise ReplayHalted("input_missing", record.path,
                               f"{record.path} is recorded in the manifest and "
                               "is not on disk")
        actual = hash_file(path)
        if actual != record.sha256:
            raise ReplayHalted(
                "input_changed", record.path,
                f"{record.path} no longer matches the manifest. Recorded "
                f"{record.sha256[:16]}, found {actual[:16]}. The run cannot be "
                "verified against inputs that have moved underneath it.",
            )


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


def _compare(manifest: RunManifest, produced: dict[str, str], kind: str
             ) -> ReplayResult:
    """Every output, by digest, with both digests kept on a mismatch."""
    matched, mismatched = [], []
    for path, text in sorted(produced.items()):
        recorded = manifest.output_named(path)
        actual = hash_text(text)
        if recorded is None:
            mismatched.append({"path": path, "expected": "not in manifest",
                               "actual": actual})
        elif recorded.sha256 == actual:
            matched.append(path)
        else:
            mismatched.append({"path": path, "expected": recorded.sha256,
                               "actual": actual})
    for recorded in manifest.outputs:
        if recorded.path not in produced:
            mismatched.append({"path": recorded.path,
                               "expected": recorded.sha256,
                               "actual": "not produced"})
    return ReplayResult(
        kind=kind,
        status="REPRODUCED" if not mismatched else "DIVERGED",
        code="outputs_match" if not mismatched else "outputs_differ",
        run_id=manifest.run_id,
        outputs_checked=len(produced),
        matched=matched,
        mismatched=mismatched,
    )


def audit_replay(manifest: RunManifest, root: str | Path) -> ReplayResult:
    """Rebuild the outputs from the stored trace. No model, no network.

    Nothing in this function constructs a client, imports one, or reads a key.
    That is the property the gate asserts by patching both the model client and
    the HTTP transport to raise: it must be impossible for this to pass because
    a call happened to succeed quietly.
    """
    root = Path(root)
    verify_inputs(manifest, root)

    trace_path = root / manifest.trace_path
    if not trace_path.exists():
        raise ReplayHalted("trace_missing", manifest.trace_path,
                           "there is no trace to replay from")
    if hash_file(trace_path) != manifest.trace_sha256:
        raise ReplayHalted(
            "trace_changed", manifest.trace_path,
            "the trace no longer matches the manifest, so it is not evidence "
            "of this run any more",
        )

    events = read_trace(trace_path)

    # The recorded responses are checked against the manifest here, offline.
    # This is what makes database drift a detectable event rather than a
    # confound: the bodies are in the trace, so the digests can be recomputed
    # years later without asking anybody's server what it says today.
    recorded = {call.identifier: call.response_sha256
                for call in manifest.external_calls}
    for event in external_responses(events):
        identifier = f"{event['endpoint']}?{event['query']}"
        digest = hash_json(event["response"])
        if recorded.get(identifier) != digest:
            raise ReplayHalted(
                "external_response_changed", identifier,
                f"the stored response for {identifier} does not hash to what "
                "the manifest recorded",
            )

    produced = outputs_from_completions(completions(events),
                                        manifest.criteria_version or 0)
    return _compare(manifest, produced, kind="audit_replay")


def verify_replay(manifest: RunManifest, root: str | Path, client: Any,
                  enrichment: Any, trace: Any,
                  configured_version: str | None = None) -> ReplayResult:
    """Re-execute the pipeline. Needs the model, and the same version of it.

    The version check is first and it refuses rather than warns. A verify
    replay against a different model version is not a failed reproduction, it
    is a different experiment, and reporting it as a failure sends somebody to
    look for a bug in code that did not change.
    """
    root = Path(root)
    verify_inputs(manifest, root)

    recorded_version = manifest.models[0].version if manifest.models else None
    current = configured_version or getattr(client, "version", None)
    if recorded_version and current and recorded_version != current:
        return ReplayResult(
            kind="verify_replay", status="REFUSED",
            code="model_version_changed", run_id=manifest.run_id,
            detail=(f"the run used version {recorded_version} and this machine "
                    f"is configured for {current}. Re-executing would compare "
                    "two different experiments. Use audit_replay, which does "
                    "not need the model at all."),
        )

    corpus = _read_json(root / "inputs/corpus.json")
    criteria = _read_json(root / "inputs/criteria.json")
    result = screen(corpus, criteria, client, enrichment, trace)
    return _compare(manifest, result["outputs"], kind="verify_replay")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """``python replay.py <run dir> [--against <run dir>]``.

    Audit replay, then the difference report if a second run is named. The
    describe() sentence goes first, always, because a reproduction claim with
    no stated conditions is not a claim.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="directory holding manifest.json")
    parser.add_argument("--against", help="a second run to compare against")
    args = parser.parse_args(argv)

    root = Path(args.run)
    manifest = load_manifest(root / "manifest.json")
    print(manifest.describe())
    print()

    try:
        result = audit_replay(manifest, root)
        print(result.render())
    except ReplayHalted as halted:
        print(f"audit_replay: HALTED ({halted.code}) on {halted.path}")
        print(f"  {halted.detail}")
        return 2

    if args.against:
        other_root = Path(args.against)
        other = load_manifest(other_root / "manifest.json")
        print()
        print(difference_report(other, manifest).render(
            include_headline=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
