"""Tests for Build 12. Nothing here reaches the network.

The desk never constructs a live client. ``TieredClient`` answers
deterministically, and the replay test patches it, ``httpx`` and the socket
layer to raise, proving the patch bites before trusting the offline replay.

``test_all_prior_gates_pass_in_sequence`` runs the other eleven builds' gates in
one subprocess, which takes most of this module's running time. It is the only
test in the repository that asserts the whole thing works at once.
"""

from __future__ import annotations

import ast
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import accounting
import desk
import httpx
import pytest
import refusals
import replay as replay_module
import stages
from checkpoints import CHECKPOINTS, CheckpointBlocked
from provenance import RunManifest
from stub_client import ModelWasCalled, TieredClient

BUILD = Path(__file__).resolve().parents[1]
REPO = BUILD.parent.parent
FIX = BUILD / "fixtures"
APPROVALS = FIX / "checkpoints"
KNOWN = FIX / "known_answer" / "shortlist.json"

PRIOR_BUILDS = [
    "01-first-agent", "02-tool-belt", "03-triage-agent", "04-dual-screen",
    "05-wrangler", "06-plate-mapper", "07-protocol-adapter", "08-dock-loop",
    "09-eln-bridge", "10-run-manifest", "11-red-team",
]

# How many tests each gate contributes. Anchored rather than counted, because
# "no failures" is silent about tests that stopped existing: a gate can lose
# half its cases and still report zero failures. Adding a test means changing
# the number here, which is the point. It is a deliberate act, recorded next
# to the eleven gates it describes, rather than a total that drifts.
EXPECTED_TESTS = {
    "01-first-agent": 11,
    "02-tool-belt": 11,
    "03-triage-agent": 14,
    "04-dual-screen": 26,
    "05-wrangler": 15,
    "06-plate-mapper": 14,
    "07-protocol-adapter": 26,
    "08-dock-loop": 19,
    "09-eln-bridge": 17,
    "10-run-manifest": 17,
    "11-red-team": 21,
    # 72, plus the 38 cases of the stack inventory gate. The mutation gate
    # is ignored below rather than counted.
    "tests": 110,
}


def a_manifest(tmp_path, client=None, approvals=None, run_id="desk-test"):
    return RunManifest(
        run_id=run_id, root=REPO, client=client or TieredClient(),
        approvals_dir=approvals or APPROVALS, workspace=tmp_path / run_id,
    )


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    """One full desk run, kept for the tests that read its manifest."""
    workspace = tmp_path_factory.mktemp("recorded")
    manifest = RunManifest(
        run_id="desk-recorded", root=REPO, client=TieredClient(),
        approvals_dir=APPROVALS, workspace=workspace / "run",
    )
    question = desk.load_question()
    shortlist = desk.run(question, manifest)
    return {"manifest": manifest, "shortlist": shortlist,
            "record": json.loads(
                (manifest.workspace / "manifest.json").read_text("utf-8"))}


def cut_the_network(monkeypatch) -> None:
    """Make every route out of the process fatal, at three layers."""
    def refuse(*args, **kwargs):
        raise ModelWasCalled("the desk reached for the network")

    monkeypatch.setattr(TieredClient, "complete", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setattr(httpx.Client, "request", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# ---------------------------------------------------------------------------
# The seven the spec names


def test_all_prior_gates_pass_in_sequence(recorded, tmp_path):
    """Eleven gates, one run, one manifest recording all of them.

    A system whose components each pass and which has never been tested end to
    end has not been tested. This is the only place in the repository where
    every gate runs together, and the desk run whose manifest records the
    result is the one the rest of this module reads.
    """
    report = tmp_path / "gates.xml"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         f"--junit-xml={report}",
         # The mutation gate runs these same eleven gates once per mutated
         # guard. Running it in here as well squares that work for no new
         # information, so it is left to the outer suite, which is where it
         # already runs.
         "--ignore=tests/test_mutation_gate.py",
         *[f"builds/{name}/tests" for name in PRIOR_BUILDS], "tests"],
        cwd=REPO, capture_output=True, text=True, timeout=1800, check=False,
    )
    assert report.exists(), result.stdout[-3000:]

    root = ElementTree.parse(report).getroot()
    per_build: dict[str, dict[str, int]] = {
        name: {"tests": 0, "failures": 0} for name in PRIOR_BUILDS
    }
    per_build["tests"] = {"tests": 0, "failures": 0}
    # pytest writes the owning module into `classname` as a dotted path, so
    # `builds.05-wrangler.tests.test_wrangler` is how a case says which build
    # it belongs to. There is no `file` attribute to read.
    for case in root.iter("testcase"):
        source = case.get("classname") or ""
        owner = next((name for name in PRIOR_BUILDS
                      if source.startswith(f"builds.{name}.")), None)
        if owner is None:
            owner = "tests" if source.startswith("tests.") else None
        if owner is None:
            continue
        per_build[owner]["tests"] += 1
        if case.find("failure") is not None or case.find("error") is not None:
            per_build[owner]["failures"] += 1

    for name, counts in sorted(per_build.items()):
        assert counts["failures"] == 0, (
            f"{name} failed {counts['failures']} of {counts['tests']}"
        )
        assert counts["tests"] == EXPECTED_TESTS[name], (
            f"{name} contributed {counts['tests']} tests and this gate expects "
            f"{EXPECTED_TESTS[name]}. If you added or removed tests, change "
            "EXPECTED_TESTS in this file to say so. A gate that accepts any "
            "number cannot tell a deleted test from a test that never was."
        )
    assert result.returncode == 0, result.stdout[-3000:]

    # One manifest records the desk run those gates were run against, and it
    # carries every fragment the earlier builds contribute.
    record = recorded["record"]
    assert record["criteria_version"] == 3
    assert record["design_ids"] == ["TMZ-NA-U87-001"]
    assert len(record["approvals"]) == 3
    assert record["inputs"] and record["outputs"]
    assert record["corpus_snapshot_id"]

    summary = {name: counts["tests"] for name, counts in per_build.items()}
    (tmp_path / "gate_summary.json").write_text(json.dumps(summary, indent=2))
    assert sum(summary.values()) == sum(EXPECTED_TESTS.values())


def test_no_stage_proceeds_past_an_unapproved_checkpoint(tmp_path):
    """Prove the prohibition bites, then assert the approved path works.

    Removing an approval must stop the run at that checkpoint and leave every
    downstream stage unexecuted. Asserting only that the approved path works
    would pass against a checkpoint that did nothing at all.
    """
    question = desk.load_question()
    downstream = {
        "screening": {"full_text_triage", "structure_acquisition", "docking",
                      "protocol_adaptation"},
        "targets": {"docking", "protocol_adaptation"},
        "shortlist": {"protocol_adaptation"},
    }

    for missing, must_not_run in downstream.items():
        empty = tmp_path / f"approvals-without-{missing}"
        empty.mkdir(parents=True)
        for name in CHECKPOINTS:
            if name != missing:
                (empty / f"{name}.json").write_bytes(
                    (APPROVALS / f"{name}.json").read_bytes()
                )

        manifest = a_manifest(tmp_path, approvals=empty,
                              run_id=f"blocked-{missing}")
        with pytest.raises(CheckpointBlocked) as raised:
            desk.run(question, manifest)
        assert raised.value.checkpoint == missing
        assert raised.value.code == "no_approval_recorded"

        ran = {stage.stage for stage in manifest.stages}
        assert not (ran & must_not_run), (
            f"{missing} was unapproved and {ran & must_not_run} ran anyway"
        )
        assert not any(a.checkpoint == missing for a in manifest.approvals)

    # An approval with no named identity is refused too, and so is one signed
    # over different content.
    tampered = tmp_path / "approvals-tampered"
    tampered.mkdir(parents=True)
    for name in CHECKPOINTS:
        body = json.loads((APPROVALS / f"{name}.json").read_text("utf-8"))
        if name == "targets":
            body["reviewed_sha256"] = "0" * 64
        (tampered / f"{name}.json").write_text(json.dumps(body))

    manifest = a_manifest(tmp_path, approvals=tampered, run_id="tampered")
    with pytest.raises(CheckpointBlocked) as raised:
        desk.run(question, manifest)
    assert raised.value.code == "approval_is_for_different_content"
    assert "docking" not in {stage.stage for stage in manifest.stages}

    # And now the approved path, which must reach the end.
    manifest = a_manifest(tmp_path, run_id="approved")
    shortlist = desk.run(question, manifest)
    assert len(manifest.approvals) == 3
    assert shortlist.candidates


def test_full_run_replays_from_manifest(recorded, tmp_path, monkeypatch):
    """The book's subtitle expressed as an assertion.

    The network is cut first, the cut is proved to bite by watching a live run
    die on it, and only then is the audit replay run. Without the middle step
    this would pass just as happily against a patch that did nothing.
    """
    record = recorded["record"]
    trace_path = recorded["manifest"].trace.path
    question = desk.load_question()

    cut_the_network(monkeypatch)

    with pytest.raises(ModelWasCalled):
        desk.run(question, a_manifest(tmp_path, run_id="should-die"))

    result = replay_module.audit_replay(
        record, trace_path, REPO, APPROVALS, tmp_path / "replay",
    )
    assert result["status"] == "REPRODUCED", result["mismatched"]
    assert result["model_calls_made"] == 0
    assert result["completions_replayed"] == sum(
        1 for event in recorded["manifest"].trace.events()
        if event["event"] == "model_call"
    )
    assert sorted(result["matched"]) == ["protocol.json", "shortlist.json"]
    assert result["shortlist"] == recorded["shortlist"].compounds()


def test_only_three_stages_are_agent_loops(recorded):
    """Walk the pipeline. Three, and the reader is meant to count them."""
    declared = [stage for stage in stages.TABLE_12_1 if stage.is_agent_loop]
    assert len(declared) == 3, [stage.name for stage in declared]
    assert {stage.name for stage in declared} == {
        "full_text_triage", "export_mapping", "protocol_adaptation"
    }

    # Declared is one thing; what the run did is another. A chain makes one
    # call per item however many items it has. A loop calls again about the
    # same item, having read what came back the first time, and that is the
    # measured difference rather than a declared one.
    manifest = recorded["manifest"]
    looped = {stage.stage for stage in manifest.stages
              if stage.max_calls_per_item > 1}
    called = {stage.stage for stage in manifest.stages if stage.model_calls}
    assert looped <= {stage.name for stage in declared}, looped

    # The printed spine runs two of the three. Export mapping is the third and
    # it runs once per instrument, which is the point of that row in the table.
    assert looped == {"full_text_triage", "protocol_adaptation"}
    assert called == {"abstract_screening", "full_text_triage",
                      "protocol_adaptation"}

    # Screening is a chain: exactly one call per record, never more.
    screening = next(stage for stage in manifest.stages
                     if stage.stage == "abstract_screening")
    assert screening.model_calls == 61
    assert screening.max_calls_per_item == 1
    assert "chain" in screening.level

    # And the desk is one function, not a coordinator. Asserted on the syntax
    # tree rather than by grepping for words: run_desk is straight-line code
    # with no loop and no branch in it, so there is nowhere for a planner to
    # live and nothing deciding which agent should handle what.
    tree = ast.parse((BUILD / "desk.py").read_text(encoding="utf-8"))
    spine = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == "run_desk")
    for node in ast.walk(spine):
        assert not isinstance(node, (ast.For, ast.While, ast.If, ast.Try)), (
            f"run_desk contains a {type(node).__name__}. The spine is meant "
            "to be a straight line; anything that branches is a planner."
        )
    called_names = sorted({
        node.func.id for node in ast.walk(spine)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    })
    assert called_names == [
        "Shortlist", "acquire_structures", "adapt_protocol", "checkpoint",
        "dock", "rank", "retrieve_corpus", "screen", "triage_agent",
    ]


def test_routing_costs_less_than_all_frontier(tmp_path):
    """The extra spend buys nothing, and the second half matters more."""
    question = desk.load_question()

    routed_client = TieredClient()
    routed = desk.run(question, a_manifest(tmp_path, client=routed_client,
                                           run_id="routed"))

    frontier_client = TieredClient(all_frontier=True)
    frontier = desk.run(question, a_manifest(tmp_path, client=frontier_client,
                                             run_id="frontier"))

    ratio = frontier_client.cost() / routed_client.cost()
    assert ratio >= 8, f"routing saved only {ratio:.1f}x"
    assert ratio <= 40, f"a {ratio:.1f}x ratio is not roughly an order of magnitude"

    # The half that matters: the answer is identical.
    assert routed.compounds() == frontier.compounds()
    assert [c.score for c in routed.candidates] == [
        c.score for c in frontier.candidates
    ]
    assert routed.protocol == frontier.protocol

    # Every token in the routed run went to a tier the stage asked for, and
    # the frontier tier saw only the one stage that is meant to reach it.
    frontier_stages = {call["stage"] for call in routed_client.calls
                       if call["tier"] == "frontier"}
    assert frontier_stages == {"protocol_adaptation"}


def test_refusals_are_refusals():
    """Table 12.3, as six functions that raise rather than six absences."""
    assert len(refusals.REFUSALS) == 6
    for name, function in refusals.REFUSALS.items():
        with pytest.raises(refusals.NotThisSystem) as raised:
            function()
        assert raised.value.capability == name
        # A refusal that does not say why is a refusal somebody works around.
        assert len(raised.value.why.split()) >= 25
        assert raised.value.as_dict()["status"] == "REFUSED"

    source = (BUILD / "refusals.py").read_text(encoding="utf-8")
    assert source.count("NotThisSystem") >= 7


def test_shortlist_matches_known_answer(recorded):
    """Compare against a shortlist produced by hand.

    This test is allowed to fail. If it does, the difference is the finding
    and the known answer is not adjusted to match the desk.

    The known answer was derived from Build 03's committed gold labels rather
    than from this desk's screening, so agreement says the desk's screening
    matched gold on the records that decide the top three, and that the
    mapping, the parsing and the ranking arithmetic are right.
    """
    known = json.loads(KNOWN.read_text(encoding="utf-8"))
    expected = known["shortlist"]
    produced = recorded["shortlist"].candidates

    assert len(produced) == len(expected) == 3
    for rank, (want, got) in enumerate(zip(expected, produced, strict=True),
                                       start=1):
        assert got.position == rank
        assert got.compound == want["compound"], (
            f"position {rank}: the hand-produced shortlist says "
            f"{want['compound']} and the desk says {got.compound}. Report the "
            "difference; do not adjust the known answer."
        )
        assert got.ligand_id == want["ligand_id"]
        assert got.score == want["score"]
        assert got.evidence_pmids == want["evidence_pmids"]

    # The finding the shortlist itself records: not one of these is an
    # antiparasitic, and the question asked about antiparasitics.
    assert "antiparasitic" in known["the_finding"]
    assert not any(c.compound in ("ivermectin", "praziquantel",
                                  "albendazole", "mebendazole")
                   for c in produced)


# ---------------------------------------------------------------------------
# The rest


def test_the_accounting_separates_measured_from_declared(recorded, tmp_path):
    manifest = recorded["manifest"]
    path = accounting.write(manifest, tmp_path / "run_accounting.md")
    text = path.read_text(encoding="utf-8")

    assert "Human minutes are **declared**, not measured" in text
    assert "not the chapter's forty minutes" in text
    for stage in manifest.stages:
        assert stage.stage in text

    summed = accounting.totals(manifest.stages)
    assert summed["declared_human_minutes"] == 180
    assert summed["model_calls"] > 0
    # Minutes and tokens are never added together.
    assert "minutes and tokens do not add" in text.lower()

    # The ninety minutes at the shortlist is the largest single block, and
    # equal to the other two checkpoints put together.
    assert CHECKPOINTS["shortlist"]["declared_minutes"] == 90
    others = [body["declared_minutes"] for name, body in CHECKPOINTS.items()
              if name != "shortlist"]
    assert CHECKPOINTS["shortlist"]["declared_minutes"] > max(others)
    assert CHECKPOINTS["shortlist"]["declared_minutes"] == sum(others)
    assert "largest single block" in text


def test_ranking_refuses_a_mixed_provenance_set():
    """Build 08's gate, still refusing nine builds later."""
    from models import DockingResult, Pose  # noqa: PLC0415

    def result(compound, source, score):
        return DockingResult(
            compound=compound, ligand_id="ACT-001", target="KIN-BETA",
            poses=[Pose(rank=1, score=score)], source=source,
            engine="recorded", seed=1, exhaustiveness=16,
        )

    mixed = [result("a", "EXPERIMENTAL", -9.0), result("b", "PREDICTED", -9.5)]
    with pytest.raises(stages.DeskRefused) as raised:
        stages.rank(mixed, require_homogeneous=True)
    assert raised.value.code == "mixed_provenance"

    allowed = stages.rank(mixed, require_homogeneous=False)
    assert allowed.homogeneous is False
    assert [c.compound for c in allowed.candidates] == ["b", "a"]


def test_the_desk_refuses_a_question_it_is_not_configured_for(tmp_path):
    question = desk.load_question()
    manifest = a_manifest(tmp_path, run_id="wrong-line")

    other = question.model_copy(update={"target_line": "HepG2"})
    with pytest.raises(stages.DeskRefused) as raised:
        desk.run(other, manifest)
    assert raised.value.code == "target_line_mismatch"

    older = question.model_copy(update={"criteria_version": 2})
    with pytest.raises(stages.DeskRefused) as raised:
        desk.run(older, a_manifest(tmp_path, run_id="wrong-criteria"))
    assert raised.value.code == "criteria_version_mismatch"


def test_input_drift_halts_the_replay(recorded, tmp_path):
    """A manifest that notices a changed input and carries on is decorative."""
    record = json.loads(json.dumps(recorded["record"]))
    record["inputs"][0]["sha256"] = "0" * 64
    with pytest.raises(replay_module.ReplayHalted) as raised:
        replay_module.audit_replay(record, recorded["manifest"].trace.path,
                                   REPO, APPROVALS, tmp_path / "drifted")
    assert raised.value.code == "input_changed"
    assert raised.value.path == recorded["record"]["inputs"][0]["path"]


def test_every_dockable_compound_can_also_be_recognised():
    """The registry and the reader have to agree, or a compound is invisible."""
    import stub_client  # noqa: PLC0415

    question = desk.load_question()
    assert set(question.compound_ligands) == set(stub_client.KNOWN_COMPOUNDS)


def test_the_trace_carries_completions_not_conclusions(recorded):
    events = recorded["manifest"].trace.events()
    calls = [event for event in events if event["event"] == "model_call"]
    assert calls
    for event in calls:
        body = json.loads(event["text"])
        assert isinstance(body, dict)
        # Raw completions: they carry the model's own words, and no field
        # this build stamped on afterwards.
        assert "criteria_version" not in body


def test_the_question_no_test_can_answer_is_in_the_readme():
    """The chapter's last question belongs to the reader, not to a gate."""
    text = (BUILD / "README.md").read_text(encoding="utf-8")
    assert "acted differently" in text
    assert re.search(r"##\s+The question no test can answer", text)


def test_this_build_imported_its_own_modules():
    # Imported inside the function on purpose, and the only place in the
    # repository that is allowed to be. A function-body import is the
    # shape that resolved to another build's module three times, so the
    # guard reproduces it rather than avoiding it.
    import desk  # noqa: PLC0415
    import models  # noqa: PLC0415
    import provenance  # noqa: PLC0415

    for module in (desk, models, provenance):
        assert Path(module.__file__).resolve().parent == BUILD
