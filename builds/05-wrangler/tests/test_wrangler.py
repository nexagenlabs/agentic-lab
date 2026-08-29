"""Tests for Build 05. Nothing here reaches the network.

The proposal step is driven by a stub, and every export is a committed fixture.
"""

import json
from pathlib import Path
from profile import profile

import pandas as pd
import pytest
from assertions import Expectation, RowConservationFailed
from models import FileMapping
from pipeline import (
    UnitCollision,
    check_expected,
    load_mapping,
    mapping_for,
    merge_tidy,
    run,
    tidy_preserving_units,
)
from propose import (
    HEAD_LINES,
    is_inferred,
    propose_mapping,
    unit_evidence_problems,
)
from schema import TidyReadings
from stub_client import UNSUPPORTED_PROPOSAL, StubClient
from transform import apply_mapping, tidy, to_csv_bytes
from validate import BOUNDS, SchemaError, validate

BUILD = Path(__file__).resolve().parents[1]
FIX = BUILD / "fixtures"
MAPPINGS = BUILD / "mappings"

BROKEN = [
    "excel_mangled", "transposed_plate", "shifted_labels",
    "unit_collision_uM", "unit_collision_nM", "extra_column",
    "percentage_as_fraction",
]

WELLS = 6
TARGETS = 1


@pytest.fixture
def wide_mapping() -> FileMapping:
    return load_mapping(MAPPINGS / "plate_wide.yaml")


@pytest.fixture
def long_mapping() -> FileMapping:
    return load_mapping(MAPPINGS / "qpcr_long.yaml")


# The six tests named in the spec.


def test_row_conservation(long_mapping):
    """Wells times targets, exactly, and any deviation itemised."""
    result = run(FIX / "qpcr_long.csv", long_mapping,
                 Expectation(wells=WELLS, targets=TARGETS))
    assert result["rows"] == WELLS * TARGETS
    assert result["wells"] == WELLS

    # A row that went missing is a failure, and the failure says what was
    # expected and what arrived rather than that something threw.
    with pytest.raises(RowConservationFailed) as caught:
        run(FIX / "qpcr_long.csv", long_mapping,
            Expectation(wells=WELLS + 1, targets=TARGETS))
    detail = caught.value.as_dict()
    assert detail["assertion"] == 1
    assert detail["expected_rows"] == 7
    assert detail["actual_rows"] == 6
    assert detail["removals"] == []


def test_unit_collision_is_caught():
    """Merging micromolar with nanomolar must raise, not concatenate."""
    left = tidy_preserving_units(FIX / "unit_collision_uM.csv",
                                 mapping_for(FIX / "unit_collision_uM.csv"))
    right = tidy_preserving_units(FIX / "unit_collision_nM.csv",
                                  mapping_for(FIX / "unit_collision_nM.csv"))
    assert "conc_uM" in left.columns
    assert "conc_nM" in right.columns

    with pytest.raises(UnitCollision) as caught:
        merge_tidy(left, right)
    message = str(caught.value)
    assert "conc_uM" in message and "conc_nM" in message
    assert "thousandfold" in message

    # And it is the collision that raises, not the merge being unable to
    # concatenate: two frames in the same unit merge without complaint.
    same = merge_tidy(right, right.copy())
    assert len(same) == 2 * len(right)


def test_schema_rejects_known_corruptions():
    """All seven broken fixtures, each firing the assertion it declares."""
    results = []
    for name in BROKEN:
        path = FIX / f"{name}.csv"
        results.append(check_expected(path, mapping_for(path)))

    slipped = [r for r in results if r["fired"] is None]
    assert not slipped, f"broken fixtures that passed: {[r['fixture'] for r in slipped]}"

    wrong = [r for r in results if r["fired"] != r["declared"]]
    assert not wrong, "\n".join(
        f"{r['fixture']}: declared {r['declared']}, fired {r['fired']}" for r in wrong
    )

    # Every fixture carries a stated reason, so a failure is a diagnosis.
    for name in BROKEN:
        declared = json.loads((FIX / f"{name}.expected.json").read_text(encoding="utf-8"))
        assert declared["breaks"].strip()
        assert declared["expected_assertion"] in (1, 2, 3, 4, 5, 6)


def test_transform_is_deterministic(long_mapping, wide_mapping):
    """The same input twice, byte for byte, column order included."""
    for path, mapping in ((FIX / "qpcr_long.csv", long_mapping),
                          (FIX / "plate_wide.csv", wide_mapping)):
        first = to_csv_bytes(validate(tidy(path, mapping)))
        second = to_csv_bytes(validate(tidy(path, mapping)))
        assert first == second
        assert first.splitlines()[0] == b"plate_id,well,compound,conc_nM,viability,replicate"


def test_unapproved_mapping_refuses(long_mapping):
    """Three lines, and they are what makes the human gate structural."""
    unapproved = long_mapping.model_copy(update={"approved_at": None})
    with pytest.raises(RuntimeError) as caught:
        apply_mapping(FIX / "qpcr_long.csv", unapproved)
    assert "Unapproved mapping" in str(caught.value)

    # A proposal arrives unapproved, so the gate is closed by default rather
    # than opened by default.
    proposed = propose_mapping(FIX / "qpcr_long.csv", StubClient(), "stub-model")
    assert proposed.approved_at is None
    assert proposed.approved_by is None
    with pytest.raises(RuntimeError):
        apply_mapping(FIX / "qpcr_long.csv", proposed)


def test_two_shapes_converge(wide_mapping, long_mapping):
    """Two instruments, two shapes, one experiment, one tidy table."""
    wide = validate(tidy(FIX / "plate_wide.csv", wide_mapping))
    long = validate(tidy(FIX / "qpcr_long.csv", long_mapping))

    pd.testing.assert_frame_equal(wide, long)
    assert to_csv_bytes(wide) == to_csv_bytes(long)
    # The long export stored micromolar and the wide one nanomolar, so the
    # convergence is only true because the conversion happened in Python.
    assert sorted(wide["conc_nM"]) == [100.0, 100.0, 1000.0, 1000.0, 10000.0, 10000.0]


# Added tests, for behaviour the spec requires but does not name a test for.


def test_the_agent_sees_fifteen_lines_and_not_the_file():
    """The bound is the point: a model shown the values forms opinions."""
    client = StubClient()
    propose_mapping(FIX / "qpcr_long.csv", client, "stub-model")
    prompt = client.messages.last_prompt

    body = pd.read_csv(FIX / "qpcr_long.csv", dtype=str)
    assert len(profile(FIX / "qpcr_long.csv")["head"]) <= HEAD_LINES
    # The whole file is seven lines, so every line is inside the bound here.
    # What matters is that the prompt carries the profile and not the frame.
    assert "FIRST LINES" in prompt
    assert str(len(body) + 1) in prompt  # the line count, as a summary
    assert "Do not convert anything" in prompt
    assert "Do not total anything" in prompt


def test_unit_evidence_must_be_checkable():
    """A claim is not evidence."""
    good = propose_mapping(FIX / "qpcr_long.csv", StubClient(), "stub-model")
    assert unit_evidence_problems(good) == []

    bad = propose_mapping(FIX / "qpcr_long.csv",
                          StubClient(UNSUPPORTED_PROPOSAL), "stub-model")
    problems = unit_evidence_problems(bad)
    assert problems
    assert "Conc (uM)" in problems[0]
    assert "without saying where it was read" in problems[0]


def test_inferred_units_are_marked_low_confidence():
    """The mapping says which units were read and which were guessed."""
    mapping = load_mapping(MAPPINGS / "qpcr_long.yaml")
    inferred = [c for c in mapping.columns if is_inferred(c.unit_evidence)]
    assert inferred, "the fixture mapping should contain at least one inference"
    for column in inferred:
        assert column.confidence == "low"
    assert unit_evidence_problems(mapping) == []

    # The phrase "not inferred" must not read as an inference. A plain
    # substring test gets this backwards and flags the best documented column
    # in the file.
    assert is_inferred("INFERRED, not read.")
    assert not is_inferred("Read from the file, not inferred: header cell.")


def test_bounds_come_from_the_printed_schema():
    """Assertion 4 reads the schema rather than a second copy of the numbers."""
    schema = TidyReadings.to_schema()
    assert set(BOUNDS) == set(schema.columns)
    assert BOUNDS["viability"].ge == -0.2, "a treated well reads below blank"
    assert BOUNDS["viability"].le == 1.5
    assert BOUNDS["conc_nM"].le == 1e7
    assert BOUNDS["well"].str_matches == r"^[A-H](0[1-9]|1[0-2])$"
    assert schema.strict is True
    assert schema.coerce is True


def test_strict_schema_rejects_an_unexpected_column(long_mapping):
    """A field added by a software update is an error, not a surprise."""
    frame = validate(tidy(FIX / "qpcr_long.csv", long_mapping))
    frame = frame.assign(temperature=37.2)
    with pytest.raises(SchemaError) as caught:
        validate(frame)
    assert any("temperature" in failure for failure in caught.value.failures)


def test_sniff_gives_up_quietly():
    """csv.Sniffer throws readily on real exports. That is not an error."""
    from profile import _sniff

    assert _sniff(["a,b,c", "1,2,3"]) == ","
    assert _sniff([]) is None
    assert _sniff([""]) is None
    assert _sniff(["Plate P001 - viability read"]) is None


def test_this_build_imported_its_own_modules():
    import pipeline
    import transform

    build_dir = Path(__file__).resolve().parents[1]
    for module in (pipeline, transform):
        assert Path(module.__file__).resolve().parent == build_dir
