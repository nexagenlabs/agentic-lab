"""Tests for Build 10. Nothing here reaches the network, and the central test
enforces that rather than assuming it.

``test_audit_replay_reproduces_outputs`` patches the model client, the HTTP
transport and the socket layer to raise before it replays anything, and it
checks that the patches bite by running the live replay through them first. A
test that passed because nothing happened to call out would establish nothing
about a machine with no key on it four years from now.
"""

from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from difference import difference_report, summarise
from hashing import hash_file, hash_json, hash_text
from models import (
    IncompleteRun,
    ManifestBuilder,
    RunManifest,
    corpus_snapshot,
    load_manifest,
    require_complete,
)
from pipeline import SUMMARY_PATH, VERDICTS_PATH, outputs_from_completions
from pydantic import ValidationError
from replay import ReplayHalted, audit_replay, verify_inputs, verify_replay
from stub_client import ForbiddenClient, ModelWasCalled, StubModel
from tracing import Trace, completions, external_responses, read_trace

BUILD = Path(__file__).resolve().parents[1]
FIX = BUILD / "fixtures"
STORED = FIX / "stored_run"
DRIFTED = FIX / "drifted_run"
DIRTY = FIX / "dirty_run"
INCOMPLETE = FIX / "incomplete_run"


def manifest_at(root: Path) -> RunManifest:
    return load_manifest(root / "manifest.json")


@pytest.fixture
def stored():
    return manifest_at(STORED)


@pytest.fixture
def drifted():
    return manifest_at(DRIFTED)


def copy_run(root: Path, tmp_path: Path) -> Path:
    destination = tmp_path / root.name
    shutil.copytree(root, destination)
    return destination


def recorded_enrichment(root: Path, manifest: RunManifest):
    """The database as it answered on the day, read back out of the trace.

    A verify replay needs the world to answer. Using the recorded responses
    rather than a live server is what lets the live replay run in the gate at
    all, and it is also the honest thing: re-executing against today's database
    would be testing two changes at once.
    """
    table: dict[str, dict] = {}
    for event in external_responses(read_trace(root / manifest.trace_path)):
        table.update(event["response"])
    return lambda batch: {record_id: table[record_id] for record_id in batch}


def cut_the_network(monkeypatch) -> None:
    """Make every route out of the process fatal.

    Three layers, because patching one proves only that one was not used. The
    model client raises, httpx raises, and the socket itself raises, so an
    import-time client or a library reaching past httpx is caught too.
    """
    def refuse(*args, **kwargs):
        raise ModelWasCalled("offline replay reached for the network")

    monkeypatch.setattr(StubModel, "complete", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setattr(httpx.Client, "request", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# ---------------------------------------------------------------------------
# The six the spec names


def test_audit_replay_reproduces_outputs(stored, monkeypatch, tmp_path):
    """The stored run, rebuilt from its trace, with no vendor and no key.

    The order matters. The network is cut first, then the cut is proved to
    bite by watching a live replay die on it, and only then is the audit
    replay run. Without the middle step this test would pass just as happily
    against a patch that did nothing.
    """
    enrichment = recorded_enrichment(STORED, stored)
    cut_the_network(monkeypatch)

    # The patches are live: a replay that needs the model dies on them. The
    # enrichment was read from the trace before the cut, so what fails below
    # is the model call and nothing incidental.
    with pytest.raises(ModelWasCalled):
        verify_replay(stored, STORED, StubModel(), enrichment,
                      Trace(run_dir=str(tmp_path / "runs")),
                      configured_version=stored.models[0].version)

    result = audit_replay(stored, STORED)

    assert result.ok, result.mismatched
    assert result.status == "REPRODUCED"
    assert result.code == "outputs_match"
    assert sorted(result.matched) == [SUMMARY_PATH, VERDICTS_PATH]
    assert result.mismatched == []

    # Every output hash, checked against the file on disk as well, so a
    # manifest that agreed with itself and not with the run would fail here.
    for record in stored.outputs:
        assert hash_file(STORED / record.path) == record.sha256


def test_manifest_detects_input_drift(stored, tmp_path):
    """One byte, and the replay halts naming the file that moved."""
    root = copy_run(STORED, tmp_path)
    target = root / "inputs/corpus.json"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("study 7 ", "study 7. "), encoding="utf-8")
    assert hash_file(target) != stored.input_named("inputs/corpus.json").sha256

    with pytest.raises(ReplayHalted) as raised:
        audit_replay(stored, root)
    assert raised.value.code == "input_changed"
    assert raised.value.path == "inputs/corpus.json"
    assert "inputs/corpus.json" in raised.value.detail
    assert raised.value.as_dict()["status"] == "HALTED"

    # A missing input halts too, and says which one rather than counting.
    (root / "inputs/criteria.json").unlink()
    with pytest.raises(ReplayHalted) as raised:
        verify_inputs(stored, root)
    assert raised.value.code in {"input_changed", "input_missing"}
    assert raised.value.path in {"inputs/corpus.json", "inputs/criteria.json"}


def test_incomplete_runs_are_marked():
    """Build 01's failure, still being guarded against nine builds later."""
    manifest = manifest_at(INCOMPLETE)
    assert manifest.status == "INCOMPLETE"
    assert manifest.halt_reason
    assert "step cap" in manifest.halt_reason
    assert not manifest.is_finished

    with pytest.raises(IncompleteRun) as raised:
        require_complete(manifest)
    body = raised.value.as_dict()
    assert body["status"] == "INCOMPLETE"
    assert body["code"] == "run_not_complete"
    assert body["answer"] is None
    assert body["halt_reason"] == manifest.halt_reason

    # It has partial outputs, which is exactly why the guard is needed: there
    # is something there to summarise, and summarising it is the failure.
    summary = json.loads(
        (INCOMPLETE / SUMMARY_PATH).read_text(encoding="utf-8")
    )
    assert summary["corpus_size"] == 20
    assert manifest.describe().endswith(f"halted because {manifest.halt_reason}.")


def test_a_complete_run_may_not_carry_a_halt_reason():
    """The one state a manifest must not be able to record.

    COMPLETE says the run finished; a halt reason says it stopped early. A
    manifest holding both hands a different answer to every consumer that
    reads it, because ``require_complete`` looks at the status and
    ``describe`` looks at the halt reason, and the consumer that reads the
    status is the one that turns partial work into a result.
    """
    body = json.loads((STORED / "manifest.json").read_text(encoding="utf-8"))
    assert body["status"] == "COMPLETE" and body["halt_reason"] is None

    body["halt_reason"] = "step cap of 20 reached with 16 records unscreened"
    with pytest.raises(ValidationError) as raised:
        RunManifest(**body)
    assert "halt_reason" in str(raised.value)

    # The state is refused wherever it is assembled, not only where it is
    # read back, so a run cannot write one and be rejected only on reload.
    builder = ManifestBuilder(
        run_id="coherence-check",
        started_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        python_version="3.11.9",
        lockfile_sha256=hash_text("lock"),
        git_commit="0" * 40,
        git_dirty=False,
    )
    with pytest.raises(ValidationError):
        builder.finish(
            status="COMPLETE",
            finished_at=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
            trace_path="trace.jsonl",
            trace_sha256=hash_text(""),
            halt_reason="step cap reached",
        )

    # Both coherent shapes still load, or the check above is refusing
    # everything and proving nothing.
    assert manifest_at(STORED).halt_reason is None
    assert manifest_at(INCOMPLETE).halt_reason


def test_dirty_tree_is_recorded():
    """Disclosed, not blocked. The run still replays; the report still says so."""
    manifest = manifest_at(DIRTY)
    assert manifest.git_dirty is True
    assert manifest.status == "COMPLETE"
    assert "a dirty tree" in manifest.describe()

    # Not blocking: the replay runs and reproduces.
    assert audit_replay(manifest, DIRTY).ok

    # And a comparison discloses it rather than swallowing it.
    report = difference_report(manifest_at(STORED), manifest)
    assert report.code.changed
    assert any("uncommitted changes" in line for line in report.code.findings)


def test_difference_report_attributes_correctly(stored, drifted):
    """The chapter's failure account, as a report somebody can act on."""
    report = difference_report(stored, drifted)

    assert report.outputs_differ == [SUMMARY_PATH, VERDICTS_PATH]
    assert report.attribution == "the world moved"

    # Four external response hashes, named individually.
    assert len(report.external_changed) == 4
    rendered = report.render()
    for entry in report.external_changed:
        assert entry["identifier"] in rendered
        assert entry["before"][:16] in rendered
        assert entry["after"][:16] in rendered
    assert "external response hashes changed: 4" in rendered

    # The code and the model did not change, and the report says so explicitly
    # rather than by omitting them.
    assert not report.code.changed
    assert not report.model.changed
    assert report.code_and_model_unchanged
    assert "CODE: unchanged" in rendered
    assert "MODEL: unchanged" in rendered
    assert "the code and the model did not change" in rendered

    # And it is not a failure, because neither run was wrong.
    assert report.is_failure is False
    assert "This is not a failure" in rendered
    assert summarise(report)["status"] == "EXPLAINED"
    assert summarise(report)["code"] == "difference_attributed"

    # The six fewer inclusions are real, and counted from the outputs.
    before = json.loads((STORED / SUMMARY_PATH).read_text(encoding="utf-8"))
    after = json.loads((DRIFTED / SUMMARY_PATH).read_text(encoding="utf-8"))
    assert before["included"] - after["included"] == 6


def test_describe_states_its_conditions(stored):
    """Nothing is reproducible in the abstract."""
    sentence = stored.describe()
    assert stored.corpus_snapshot_id in sentence
    assert stored.git_commit in sentence
    for use in stored.models:
        assert f"{use.id}@{use.version}" in sentence
    assert "COMPLETE" in sentence

    # A manifest with no snapshot says so rather than reading as though it had
    # one, because a blank in this sentence is the whole point of the field.
    without = stored.model_copy(update={"corpus_snapshot_id": ""})
    assert "UNRECORDED" in without.describe()


# ---------------------------------------------------------------------------
# The rest


def test_the_trace_stores_completions_not_conclusions(stored):
    """The property audit replay rests on, asserted directly.

    If the trace held verdicts rather than the model's own words, the replay
    below would be checking that a summary was copied correctly rather than
    that the outputs follow from what the model said.
    """
    events = read_trace(STORED / stored.trace_path)
    texts = completions(events)
    assert len(texts) == 36

    for text in texts:
        parsed = json.loads(text)
        # Raw completion text, not a build-side conclusion: it carries the
        # model's own reason and confidence, and no criteria_version, which is
        # stamped on by the pipeline afterwards.
        assert set(parsed) == {"id", "decision", "reason", "confidence"}

    rebuilt = outputs_from_completions(texts, stored.criteria_version)
    assert hash_text(rebuilt[VERDICTS_PATH]) == \
        stored.output_named(VERDICTS_PATH).sha256


def test_verify_replay_reproduces_when_the_model_is_available(stored, tmp_path):
    """The other replay: re-execute, and get the same outputs."""
    trace = Trace(run_dir=str(tmp_path / "runs"))
    result = verify_replay(stored, STORED, StubModel(),
                           recorded_enrichment(STORED, stored), trace,
                           configured_version="2026-05-01")
    assert result.ok
    assert result.kind == "verify_replay"
    assert sorted(result.matched) == [SUMMARY_PATH, VERDICTS_PATH]


def test_verify_replay_refuses_a_different_model_version(stored, tmp_path):
    """A different version is a different experiment, not a failed replay."""
    result = verify_replay(stored, STORED, StubModel(),
                           recorded_enrichment(STORED, stored),
                           Trace(run_dir=str(tmp_path / "runs")),
                           configured_version="2027-01-01")
    assert result.status == "REFUSED"
    assert result.code == "model_version_changed"
    assert "audit_replay" in result.detail
    assert not result.ok


def test_outputs_differing_with_nothing_moved_is_the_alarming_case(stored):
    """The case that deserves alarm, distinguished from the one that does not.

    Same code, same model, same corpus, different outputs. Something that
    determines the result is not in the manifest, and that is worse news than
    four database rows having been revised.
    """
    twin = stored.model_copy(update={
        "run_id": "run-twin",
        "outputs": [record.model_copy(update={"sha256": "0" * 64})
                    for record in stored.outputs],
    })
    report = difference_report(stored, twin)
    assert report.is_failure is True
    assert "unexplained" in report.attribution
    assert summarise(report)["code"] == "unexplained_divergence"
    assert "not in the manifest" in report.verdict


def test_two_identical_runs_report_no_difference(stored):
    report = difference_report(stored, stored)
    assert report.outputs_differ == []
    assert report.is_failure is False
    assert report.attribution == "nothing moved, and the outputs agree"
    assert "The run reproduces." in report.render()


def test_the_corpus_snapshot_moves_when_the_world_does(stored, drifted):
    """The field the printed listing does not carry, doing its job."""
    assert stored.corpus_snapshot_id != drifted.corpus_snapshot_id
    assert stored.inputs[0].sha256 == drifted.inputs[0].sha256

    recomputed = corpus_snapshot(stored.inputs, stored.external_calls)
    assert recomputed == stored.corpus_snapshot_id

    # Order in, same identifier out. A snapshot that depended on read order
    # would report drift that was entirely an artefact of the writer.
    shuffled = corpus_snapshot(list(reversed(stored.inputs)),
                               list(reversed(stored.external_calls)))
    assert shuffled == stored.corpus_snapshot_id


def test_every_input_and_output_carries_bytes_beside_its_digest(stored):
    """A truncated file is visible without rehashing four gigabytes."""
    for record in stored.inputs:
        path = STORED / record.path
        assert record.bytes == path.stat().st_size
        assert record.sha256 == hash_file(path)
    for record in stored.outputs:
        path = STORED / record.path
        assert record.bytes == path.stat().st_size


def test_external_responses_are_hashed_and_the_bodies_are_kept(stored):
    """What makes database drift detectable rather than a confound."""
    events = external_responses(read_trace(STORED / stored.trace_path))
    assert len(events) == 6
    recorded = {call.identifier: call.response_sha256
                for call in stored.external_calls}
    for event in events:
        identifier = f"{event['endpoint']}?{event['query']}"
        assert recorded[identifier] == hash_json(event["response"])


def test_a_forbidden_client_raises_on_any_use():
    """The instrument the offline test relies on, checked rather than trusted."""
    client = ForbiddenClient()
    with pytest.raises(ModelWasCalled):
        _ = client.complete
    with pytest.raises(ModelWasCalled):
        client()


def test_this_build_imported_its_own_modules():
    # Imported inside the function on purpose, and the only place in the
    # repository that is allowed to be. A function-body import is the
    # shape that resolved to another build's module three times, so the
    # guard reproduces it rather than avoiding it.
    import hashing  # noqa: PLC0415
    import models  # noqa: PLC0415
    import replay  # noqa: PLC0415

    build_dir = Path(__file__).resolve().parents[1]
    for module in (hashing, models, replay):
        assert Path(module.__file__).resolve().parent == build_dir
