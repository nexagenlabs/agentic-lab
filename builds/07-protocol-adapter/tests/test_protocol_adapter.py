"""Tests for Build 07. Nothing here reaches the network.

The model step is driven by ``stub_client.StubClient``, which replays a
recorded reading of each protocol. One of those recordings deliberately
invents a number, because a stub that only ever behaves is a stub that proves
nothing about the checks it is meant to exercise.
"""

import json
from pathlib import Path

import pytest
from adapt import (
    classify,
    load_lines,
    run_adaptation,
    scale_seeding_density,
)
from extract import verify
from models import (
    MANDATORY_PARAMETERS,
    Adaptation,
    AdapterError,
    ExtractedParameter,
    ParameterChange,
)
from pydantic import ValidationError
from report import CATEGORIES, empty_categories, render_report, write_report
from source import load_protocol
from stub_client import StubClient

BUILD = Path(__file__).resolve().parents[1]
FIX = BUILD / "fixtures"
PROTOCOLS = FIX / "source_protocols"
EXPECTED = FIX / "expected"
LINES = FIX / "target_lines.json"

MODEL = "stub-model"

PAIRINGS = sorted(EXPECTED.glob("*.json"))


@pytest.fixture
def client():
    return StubClient()


def adapt(name: str, target: str, client) -> object:
    return run_adaptation(
        PROTOCOLS / f"{name}.md", target, client, MODEL, lines_path=LINES,
    )


# The five tests named in the spec.


@pytest.mark.parametrize("declared_path", PAIRINGS, ids=lambda p: p.stem)
def test_every_table_parameter_is_classified(declared_path, client):
    """All six, in exactly one list, for every source and target pairing."""
    declared = json.loads(declared_path.read_text(encoding="utf-8"))
    name = declared["source_protocol"].removesuffix(".md")
    run = adapt(name, declared["target_cell_line"], client)
    result = run.adaptation.as_dict()

    seen = (
        [change["parameter"] for change in result["changed"]]
        + result["carried_over_unchanged"]
        + result["not_stated_in_source"]
        + result["requires_human_decision"]
    )
    assert sorted(seen) == sorted(MANDATORY_PARAMETERS)

    assert sorted(c["parameter"] for c in result["changed"]) == declared["changed"]
    for key in ("carried_over_unchanged", "not_stated_in_source",
                "requires_human_decision"):
        assert result[key] == declared[key], (
            f"{declared_path.stem}, {key}: expected {declared[key]}, "
            f"got {result[key]}"
        )


def test_a_parameter_in_none_or_two_lists_raises():
    """The validator, on its own, without a protocol anywhere near it."""
    complete = {
        "source_doi": "10.5555/agenticlab.2026.00711",
        "source_cell_line": "GBM-4471",
        "target_cell_line": "GBM-2209",
        "changed": [],
        "carried_over_unchanged": list(MANDATORY_PARAMETERS),
        "not_stated_in_source": [],
        "requires_human_decision": [],
    }
    Adaptation(**complete)   # the complete case is accepted

    missing = dict(complete)
    missing["carried_over_unchanged"] = [
        p for p in MANDATORY_PARAMETERS if p != "seeding_density"
    ]
    with pytest.raises(ValidationError) as caught:
        Adaptation(**missing)
    assert "seeding_density" in str(caught.value)
    assert "none of the four lists" in str(caught.value)

    twice = dict(complete)
    twice["not_stated_in_source"] = ["seeding_density"]
    with pytest.raises(ValidationError) as caught:
        Adaptation(**twice)
    assert "more than one list" in str(caught.value)

    # A misspelling is silence wearing a disguise, so it is refused as both.
    typo = dict(complete)
    typo["carried_over_unchanged"] = [
        p for p in MANDATORY_PARAMETERS if p != "seeding_density"
    ] + ["seeding density"]
    with pytest.raises(ValidationError) as caught:
        Adaptation(**typo)
    assert "misspellings" in str(caught.value)


def test_silence_is_reported_not_defaulted(client):
    """The protocol that omits seeding density and endpoint."""
    run = adapt("omits_density_and_endpoint", "NSC-8810", client)
    adaptation = run.adaptation

    assert "seeding_density" in adaptation.not_stated_in_source
    assert "incubation_to_endpoint" in adaptation.not_stated_in_source

    # Neither was given a value on the way past.
    for parameter in ("seeding_density", "incubation_to_endpoint"):
        assert run.readings[parameter].stated is False
        assert run.readings[parameter].value is None
        assert parameter not in adaptation.carried_over_unchanged
        assert all(c.parameter != parameter for c in adaptation.changed)

    # And the report says so in words rather than leaving a gap.
    text = render_report(run)
    assert "**seeding density**: **not stated in the source.**" in text
    assert "Nothing was substituted for it." in text


def test_carryover_is_explicit(client):
    """Chapter 6's failure account, as a test.

    The adapter that changed the concentrations and silently kept the seeding
    density is the one this build exists to stop. A different doubling time
    means the density is either adapted with the arithmetic or handed over.
    """
    for target in ("GBM-2209", "NSC-8810", "HEP-3355"):
        run = adapt("full_disclosure", target, client)
        adaptation = run.adaptation

        assert "seeding_density" not in adaptation.carried_over_unchanged, (
            f"seeding density carried over into {target}, which doubles at a "
            "different rate. This is the failure the chapter opens with."
        )
        changed = {c.parameter: c for c in adaptation.changed}
        if "seeding_density" in changed:
            change = changed["seeding_density"]
            assert change.rationale.strip()
            assert "doubl" in change.rationale
            assert change.adapted_value != change.source_value
        else:
            assert "seeding_density" in adaptation.requires_human_decision

    # Adapting to the line the work was done in changes nothing, and that is
    # the case where carrying over is honest rather than careless.
    same = adapt("full_disclosure", "GBM-4471", client)
    assert "seeding_density" in same.adaptation.carried_over_unchanged


def test_ambiguous_source_does_not_invent(client):
    """'An appropriate density' is silence, not a number."""
    run = adapt("ambiguous_density", "NSC-8810", client)

    assert "seeding_density" in run.adaptation.not_stated_in_source
    assert "passage_number_range" in run.adaptation.not_stated_in_source
    assert run.readings["seeding_density"].value is None

    # The recorded extraction did answer 5000. It was the verification that
    # refused it, not the prompt, and the refusal is on the record.
    refused = {claim["parameter"]: claim for claim in run.rejected_claims}
    assert refused["seeding_density"]["claimed_value"] == "5000 cells per well"
    assert refused["seeding_density"]["code"] == "value_not_supported_by_evidence"
    assert refused["passage_number_range"]["code"] == (
        "value_not_supported_by_evidence"
    )

    # 5000 appears nowhere in the adaptation it produced.
    assert "5000" not in json.dumps(run.adaptation.as_dict())


def test_report_names_empty_categories(client, tmp_path):
    """A heading with nothing under it is the most informative line."""
    run = adapt("omits_density_and_endpoint", "GBM-2209", client)
    path = write_report(run, tmp_path / "adaptation_report.md")
    text = path.read_text(encoding="utf-8")

    # Every category is printed, empty or not.
    for category in CATEGORIES:
        assert f"## {category}" in text

    empty = empty_categories(run)
    # Design holds only the endpoint, which this protocol never states.
    assert "Design" in empty
    # Two categories hold nothing this adapter classifies, ever.
    assert "Analysis" in empty
    assert "Data availability" in empty
    # And the source names its line without an RRID.
    assert "Cell source and identity" in empty

    for category in empty:
        assert f"- **{category}**" in text
    assert "An absent category is the useful output." in text


# Added tests, for behaviour the spec requires but does not name a test for.


def test_the_seeding_arithmetic_is_arithmetic():
    """Taken in Python, and checked against a case done by hand.

    Over 72 h a line doubling every 22 h completes 3.2727 doublings and one
    doubling every 44 h completes 1.6364, a difference of 1.6364. Two to that
    power is 3.1088, so 3000 cells per well becomes 9326.
    """
    adapted = scale_seeding_density(3000.0, 22.0, 44.0, 72.0)
    assert round(adapted) == 9326

    # A line that grows at the same rate needs no change at all.
    assert scale_seeding_density(3000.0, 22.0, 22.0, 72.0) == 3000.0

    # And a faster target is seeded more sparsely, not more densely.
    assert scale_seeding_density(3000.0, 34.0, 22.0, 72.0) < 3000.0


def test_seeding_density_needs_a_source_doubling_time(client):
    """No lookup, no arithmetic, and no silent carry-over either."""
    run = adapt("full_disclosure", "NSC-8810", client)
    readings = run.readings
    placement, changes = classify(readings, None, run.target)
    assert placement["seeding_density"] == "requires_human_decision"
    assert all(c.parameter != "seeding_density" for c in changes)


def test_evidence_must_come_from_the_protocol(client):
    """A quotation that is not in the paper is not a quotation."""
    protocol = load_protocol(PROTOCOLS / "full_disclosure.md")
    invented = [ExtractedParameter(
        parameter="serum_concentration", stated=True, value="10 %",
        evidence="Cells were grown in 10 % serum, as everyone does.",
    )]
    verified, rejected = verify(protocol, invented)
    assert verified[0].stated is False
    assert rejected[0]["code"] == "evidence_not_in_source"


def test_an_unknown_target_line_is_refused(client):
    """A line with no record has no RRID and no doubling time."""
    with pytest.raises(AdapterError) as caught:
        adapt("full_disclosure", "GBM-0000", client)
    assert caught.value.code == "unknown_target_line"
    assert caught.value.as_dict()["status"] == "ERROR"


def test_every_line_record_carries_an_rrid():
    """Identity again, as in Build 06."""
    lines = load_lines(LINES)
    assert len(lines) == 4
    for line in lines.values():
        assert line.rrid.startswith("CVCL_")
        assert line.doubling_time_h > 0


def test_the_model_is_never_asked_to_adapt_anything(client):
    """One prompt per adaptation, and it asks for readings only."""
    adapt("full_disclosure", "NSC-8810", client)
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "do not adapt anything to another cell line" in prompt.lower()
    assert "do not convert units" in prompt.lower()
    # The target line is never mentioned, so the model cannot adapt towards it
    # even if it wanted to.
    assert "NSC-8810" not in prompt


def test_the_trace_is_jsonl(client, tmp_path):
    """One event per line, from the first version."""
    import tracing

    trace = tracing.Trace(run_dir=tmp_path / "runs")
    run_adaptation(PROTOCOLS / "ambiguous_density.md", "NSC-8810", client,
                   MODEL, lines_path=LINES, trace=trace)
    events = [json.loads(line) for line in
              trace.path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "adaptation_started"
    assert "claim_rejected" in {e["event"] for e in events}
    assert events[-1]["event"] == "adaptation_complete"


def test_a_change_records_a_rationale_and_a_confidence(client):
    """A diff with no reasons in it is a list, not a diff."""
    run = adapt("full_disclosure", "NSC-8810", client)
    assert run.adaptation.changed
    for change in run.adaptation.changed:
        assert isinstance(change, ParameterChange)
        assert len(change.rationale.split()) >= 8
        assert change.confidence in ("high", "low")


def test_this_build_imported_its_own_modules():
    import adapt as adapt_module
    import report

    build_dir = Path(__file__).resolve().parents[1]
    for module in (adapt_module, report):
        assert Path(module.__file__).resolve().parent == build_dir
