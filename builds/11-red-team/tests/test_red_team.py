"""Tests for Build 11. Nothing here reaches the network.

Every earlier build runs in a subprocess with one build folder on its path and
its own offline stubs wired, exactly as that build's own tests wire them. No
build module is imported into this process, which is how a harness can measure
five builds without breaking the one-build-at-a-time invariant.

Two module-scoped fixtures hold the worker processes open, because starting a
Python interpreter per fault would make a thirty-one fault run slower than it
needs to be for no gain in what it measures.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import catalogue
import drift as drift_module
import pytest
from families import UnknownFamily, known_families, register_family
from harness import Fault, FaultResult, Report, run_red_team
from manifest import record, write
from pydantic import ValidationError

FAMILIES = ["fabrication", "numeric", "drift", "loop", "identity"]

# Passed in rather than defaulted, so a reader can disagree with it. Build 05
# and Build 06 between them catch five of the six numeric faults unaided, and
# the sixth needs a check this build adds.
NUMERIC_THRESHOLD = 0.8


@pytest.fixture(scope="module")
def checked():
    """The earlier builds with this build's checks attached."""
    pipelines = {family: catalogue.checked_pipeline(family)
                 for family in FAMILIES}
    yield pipelines
    for pipeline in pipelines.values():
        pipeline.close()


@pytest.fixture(scope="module")
def bare():
    """The earlier builds exactly as they are. What a reader has today."""
    pipelines = {family: catalogue.bare_pipeline(family) for family in FAMILIES}
    yield pipelines
    for pipeline in pipelines.values():
        pipeline.close()


def run(pipelines, family, faults=None) -> Report:
    return run_red_team(
        pipelines[family],
        faults if faults is not None else catalogue.planted(family),
        catalogue.CLEAN_INPUTS[family](),
    )


def result_for(report: Report, fault_id: str) -> FaultResult:
    for entry in report.results:
        if entry.fault_id == fault_id:
            return entry
    raise AssertionError(f"{fault_id} is not in the report")


# ---------------------------------------------------------------------------
# The six the spec names


def test_every_planted_fabrication_is_caught(checked):
    """No tolerance. A reference either resolves or it does not.

    Existence checking is the one part of this chapter that is solved, so a
    rate below 1.0 here is a bug in the checker rather than a limit of the
    method.
    """
    report = run(checked, "fabrication")
    caught, planted = report.rate()
    assert planted == 5
    assert caught == planted, [entry.fault_id for entry in report.missed]
    assert report.silent_misses == []

    # Each fault was caught by the check it named, not by something else that
    # happened to fire. A rate of 1.0 assembled from the wrong checks would
    # pass a weaker assertion than this one.
    for fault in catalogue.planted("fabrication"):
        assert fault.should_be_caught_by in result_for(report, fault.fault_id).fired


def test_numeric_faults_detected_above_threshold(checked):
    report = run(checked, "numeric")
    caught, planted = report.rate()
    assert planted == 6
    assert caught / planted >= NUMERIC_THRESHOLD, report.summary()

    # Separately, and this is the assertion that matters more: nothing went
    # through while the run reported success. The thousandfold unit error is
    # the one that does, and it does so past every one of Build 05's six
    # assertions, which is why unit_plausibility exists.
    assert report.silent_misses == []


def test_drift_is_detected_before_output(checked):
    """Detection after the output is written is not detection.

    The drift check runs before the pipeline is dispatched, so the ordering is
    a property of ``GuardedPipeline`` rather than a claim. The assertion is on
    the event order the run actually produced.
    """
    report = run(checked, "drift")
    assert report.rate() == (5, 5), report.summary()

    pipeline = catalogue.checked_pipeline("drift")
    try:
        job = catalogue.planted("drift")[2].inject(catalogue.clean_drift())
        outcome = pipeline.run(job)
    finally:
        pipeline.close()

    assert "drift_from_origin" in outcome.checks_fired
    fired_at = outcome.events.index("drift_check_fired")
    written_at = outcome.events.index("summary_written")
    assert fired_at < written_at, outcome.events


def test_detection_rate_is_reported_not_asserted(checked, tmp_path):
    """The full rate reaches the manifest, including everything it missed."""
    report = None
    for family in FAMILIES:
        family_report = run(checked, family)
        report = family_report if report is None else report.combined(family_report)

    run_record = record("redteam-test", "earlier builds plus this build's "
                        "checks", report, started_at=datetime.now(timezone.utc))
    path = write(run_record, tmp_path / "manifest.json")
    body = json.loads(path.read_text(encoding="utf-8"))

    assert body["planted"] == 25
    assert body["caught"] == report.caught
    assert set(body["by_family"]) == set(FAMILIES)
    for family in FAMILIES:
        assert body["by_family"][family]["planted"] > 0

    # Every fault appears, caught or not, and the summary carries its
    # denominator rather than a bare fraction.
    assert len(body["results"]) == 25
    assert "of" in body["summary"] and "families" in body["summary"]
    assert "missed" in body and "silent_misses" in body

    # There is no scalar detection rate anywhere in the manifest, on purpose.
    assert "detection_rate" not in body
    assert not any(isinstance(value, float) for value in body.values())


def test_negative_controls_do_not_fire(checked):
    """A harness that fires on everything has a rate of 1.0 and is useless."""
    for family in FAMILIES:
        controls = catalogue.controls(family)
        assert controls, f"{family} has no negative control"
        report = run(checked, family, faults=controls)
        for entry in report.results:
            assert entry.fired == [], (
                f"{entry.fault_id} is a clean input and {entry.fired} fired "
                "on it. A false positive here costs more than a miss, because "
                "it is what teaches somebody to stop reading the output."
            )


def test_families_are_open():
    """A sixth family can be registered without editing any model."""
    assert "identity" in known_families()
    assert "identity" not in Fault.model_fields["family"].annotation.__args__

    before = len(known_families())
    register_family(
        "provenance",
        "Claims whose source cannot be reconstructed from the manifest, "
        "which is a distinct failure from a fabricated citation.",
    )
    assert "provenance" in known_families()
    assert len(known_families()) == before + 1

    fault = catalogue.OpenFault(
        fault_id="provenance-01", family="provenance",
        description="a claim with no recorded source",
        inject=lambda job: job, should_be_caught_by="source_recorded",
    )
    assert fault.family == "provenance"

    # Pydantic wraps the UnknownFamily raised in the validator, which is the
    # right behaviour: the caller gets one error type from model construction.
    with pytest.raises(ValidationError) as raised:
        catalogue.OpenFault(
            fault_id="invented-01", family="invented",
            description="a family nobody registered",
            inject=lambda job: job, should_be_caught_by="nothing",
        )
    assert "not a registered family" in str(raised.value)

    # A family with no written reason is refused, because the chapter's
    # failure was a missing category rather than a missing check.
    with pytest.raises(UnknownFamily):
        register_family("terse", "because")


# ---------------------------------------------------------------------------
# Proving the harness bites


@pytest.mark.parametrize("family", FAMILIES)
def test_each_family_has_a_fault_the_bare_builds_miss(bare, family):
    """The CLAUDE.md rule, applied to the harness itself.

    A red team that only ever reports successes has reproduced this chapter's
    failure one level up. For every family there is a fault the earlier builds
    miss on their own, and it is asserted rather than assumed: if a later
    change made one of these pass, this fails and somebody has to decide
    whether the check is real or the fault stopped being one.
    """
    missed_id = catalogue.KNOWN_MISSED_BY_BUILD[family]
    fault = next(f for f in catalogue.FAULTS[family]()
                 if f.fault_id == missed_id)
    report = run(bare, family, faults=[fault])
    entry = report.results[0]
    assert not entry.caught, (
        f"{missed_id} is recorded as a fault the bare builds miss, and it "
        f"fired {entry.fired}. Either a check was added or the fault stopped "
        "being one."
    )
    assert entry.silent, (
        f"{missed_id} was missed and the run did not complete, so it is a "
        "nuisance rather than the failure this book is about"
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_each_family_has_a_fault_something_catches(bare, checked, family):
    """And one that is caught, so the harness is not measuring a no-op."""
    caught_id = catalogue.KNOWN_CAUGHT_BY_BUILD[family]
    if caught_id is None:
        # Recorded as an absence rather than glossed over: the bare builds
        # catch nothing in this family at all, which is the finding.
        report = run(bare, family)
        assert report.caught == 0, (
            f"{family} is recorded as a family the bare builds catch nothing "
            f"in, and they caught {report.caught}. Update the catalogue."
        )
        checked_report = run(checked, family)
        assert checked_report.caught == len(checked_report.results)
        return

    fault = next(f for f in catalogue.FAULTS[family]()
                 if f.fault_id == caught_id)
    report = run(bare, family, faults=[fault])
    assert report.results[0].caught, (
        f"{caught_id} is recorded as caught by the bare builds and was not. "
        "The harness may be measuring a check that no longer runs."
    )


def test_the_added_checks_are_what_close_the_gap(bare, checked):
    """The bare builds miss most of it. That is the finding, asserted.

    If this ever stops being true, either an earlier build grew a check, which
    is good news worth noticing, or this build started measuring itself.
    """
    bare_caught = sum(run(bare, family).caught for family in FAMILIES)
    checked_caught = sum(run(checked, family).caught for family in FAMILIES)
    assert bare_caught < checked_caught
    assert bare_caught == 11
    assert checked_caught == 25


def test_the_wrong_drift_check_reports_nothing():
    """The argument of drift.py, as an executable demonstration.

    Fault drift-04 walks from screening a corpus to comparing plasma protein
    binding. Compared with the origin it is plainly gone. Compared step to
    step, no adjacent pair differs enough to notice, which is what a check
    built the obvious way would report all the way down.
    """
    job = next(f for f in catalogue.FAULTS["drift"]()
               if f.fault_id == "drift-04").inject(catalogue.clean_drift())
    steps = job["state"]["steps"]

    against_origin = drift_module.drift_check(job["origin"], job["state"])
    assert "drift_from_origin" in against_origin.checks_fired

    step_to_step = drift_module.step_to_step_check(steps)
    assert step_to_step.checks_fired == [], (
        "the step-to-step check fired, which would make the point of "
        "drift.py harder to demonstrate rather than easier"
    )
    assert step_to_step.overlap > against_origin.overlap


def test_silent_misses_are_counted_separately_from_crashes(bare):
    """A miss that crashes is a nuisance. A miss that completes is the book."""
    report = None
    for family in FAMILIES:
        family_report = run(bare, family)
        report = family_report if report is None else report.combined(family_report)

    assert report.missed, "the bare builds are supposed to miss things"
    # Every single miss by the bare builds is silent: the run completed, an
    # answer came back, and nothing said anything was wrong.
    assert len(report.silent_misses) == len(report.missed)
    assert len(report.silent_misses) == 14


def test_the_summary_never_reports_a_bare_fraction():
    report = Report(results=[
        FaultResult(fault_id="numeric-01", caught=True, fired=["x"],
                    silent=False),
        FaultResult(fault_id="loop-01", caught=False, fired=[], silent=True),
    ])
    summary = report.summary()
    assert summary == "1 of 2, across 2 families; 1 silent"
    assert "50" not in summary and "0.5" not in summary
    assert report.rate() == (1, 2)
    assert not hasattr(report, "detection_rate")


def test_this_build_imported_its_own_modules():
    # Imported inside the function on purpose, and the only place in the
    # repository that is allowed to be. A function-body import is the
    # shape that resolved to another build's module three times, so the
    # guard reproduces it rather than avoiding it.
    import catalogue  # noqa: PLC0415
    import harness  # noqa: PLC0415
    import identity  # noqa: PLC0415

    build_dir = catalogue.HERE
    for module in (catalogue, harness, identity):
        assert str(build_dir) in str(module.__file__)
