"""Tests for Build 06. Nothing here reaches the network.

There is no model call anywhere in this build, so there is no stub client to
drive: every check is arithmetic and every input is a committed file.
"""

import json
from pathlib import Path

import pytest
from checks import EXPECTED_IC50, MIN_RELIABLE_UL, check_dilution_series
from commitment import CommitmentError, check_commitment_precedes_data
from design import DesignError, load_design
from layout import build_layout, perimeter_wells, well_balance
from review import ReviewFailed, review_design
from synergy import (
    ConsensusRefused,
    SynergyModelRefused,
    check_consensus,
    choose_synergy_model,
)

BUILD = Path(__file__).resolve().parents[1]
DESIGN = BUILD / "designs" / "tmz_na_u87mg.yaml"
BAD = BUILD / "fixtures" / "bad_designs"
RESULTS = BUILD / "fixtures" / "results"

BAD_DESIGNS = [
    "no_rrid", "solvent_above_tolerance", "transfer_below_minimum",
    "no_lower_plateau", "wells_do_not_balance", "no_synergy_model",
    "commitment_after_data",
]


@pytest.fixture
def design():
    return load_design(DESIGN)


# The eight tests named in the spec.


def test_dilution_series_is_physical(design):
    """Volumes, solvent and span, all computed before anything is pipetted."""
    limit = design.controls.vehicle.final_pct

    # The printed design does trip the solvent check: 800 uM from a 100 mM
    # stock needs 0.8 per cent DMSO against a 0.5 per cent limit.
    tmz = design.axes["drug_a"]
    problems = check_dilution_series(tmz.name, tmz.top_conc_uM,
                                     tmz.dilution_factor, tmz.n_steps,
                                     stock_mM=100.0, transfer_uL=100.0,
                                     max_solvent_pct=limit)
    assert any("solvent" in problem for problem in problems)

    # A stock ten times stronger clears it, and then the series is physical.
    clean = check_dilution_series(tmz.name, tmz.top_conc_uM,
                                  tmz.dilution_factor, tmz.n_steps,
                                  stock_mM=1000.0, transfer_uL=100.0,
                                  max_solvent_pct=limit)
    assert clean == []

    # Both axes span their expected IC50 with a point each side.
    for axis in design.axes.values():
        series = axis.series_uM()
        floor = EXPECTED_IC50[axis.name]
        assert min(series) < floor < max(series), (
            f"{axis.name} does not straddle its expected IC50: "
            f"{min(series)} to {max(series)} against {floor}"
        )

    # And a transfer below the pipetting floor is refused.
    thin = check_dilution_series(tmz.name, tmz.top_conc_uM, tmz.dilution_factor,
                                 tmz.n_steps, stock_mM=1000.0,
                                 transfer_uL=MIN_RELIABLE_UL / 2,
                                 max_solvent_pct=limit)
    assert any("pipetting" in problem for problem in thin)


def test_well_count_balances(design):
    """Every well on every plate is accounted for, exactly."""
    layout = build_layout(design)
    assert well_balance(layout, design) == []

    expected_perimeter = len(perimeter_wells(design.rows, design.columns))
    for plate in range(1, layout.plates + 1):
        counts = layout.counts(plate)
        assigned = (
            counts.get("treatment", 0)
            + counts.get("unused", 0)
            + counts.get("vehicle", 0)
            + counts.get("untreated", 0)
            + counts.get("blank", 0)
            + counts.get("excluded_perimeter", 0)
        )
        assert assigned == design.plate_format
        assert counts.get("excluded_perimeter", 0) == expected_perimeter
        # Controls on every plate, not a reference plate.
        assert counts.get("vehicle", 0) == design.controls.vehicle.wells
        assert counts.get("untreated", 0) == design.controls.untreated.wells
        assert counts.get("blank", 0) == design.controls.blank.wells

    # Every treatment well the design asks for is somewhere.
    treatments = [a for a in layout.assignments if a.role == "treatment"]
    assert len(treatments) == design.treatment_wells


def test_synergy_model_committed_before_data(design):
    """The whole point of the chapter."""
    assert design.analysis is not None
    assert design.analysis.synergy_model == "bliss"
    assert len(design.analysis.justification.split()) >= 8
    assert "mechanism" in design.analysis.justification.lower() or \
           "mechanisms" in design.analysis.justification.lower()

    result = check_commitment_precedes_data(DESIGN, RESULTS)
    assert result["readings"] == 3
    assert result["margin_hours"] > 0
    assert "before any data" in result["verdict"]

    # And the reverse case fails rather than warning.
    with pytest.raises(CommitmentError) as caught:
        check_commitment_precedes_data(BAD / "commitment_after_data.yaml", RESULTS)
    assert caught.value.failure == "commitment_after_data"
    assert "no trace" in caught.value.detail


def test_rrid_is_required():
    """A name is a label, and labels have been wrong."""
    with pytest.raises(DesignError) as caught:
        load_design(BAD / "no_rrid.yaml")
    assert caught.value.failure == "no_rrid"
    assert "CVCL" in caught.value.detail
    assert "misidentified" in caught.value.detail

    # The identifier has to look like one, not merely be present.
    good = load_design(DESIGN)
    assert good.rrid == "CVCL_0022"


def test_model_selection_is_refused():
    """The build will not make a mechanistic claim on your behalf."""
    with pytest.raises(SynergyModelRefused) as caught:
        choose_synergy_model()
    message = str(caught.value)
    assert "will not choose" in message
    assert "four chances at a positive result" in message
    # The message explains what the models actually claim, so the refusal is
    # useful rather than merely obstructive.
    for model in ("Bliss", "Loewe", "HSA", "ZIP"):
        assert model in message


def test_bliss_and_zip_not_both_in_consensus():
    """ZIP already contains the Bliss claim, so the pair double-counts it."""
    with pytest.raises(ConsensusRefused) as caught:
        check_consensus(["bliss", "zip", "hsa"])
    message = str(caught.value)
    assert "SynergyFinder" in message
    assert "interpolat" in message

    # Independent pairs are fine.
    check_consensus(["bliss", "loewe"])
    check_consensus(["hsa", "zip"])

    with pytest.raises(ConsensusRefused):
        check_consensus(["bliss"])


def test_layout_is_reproducible(design):
    """A layout you cannot reproduce is one nothing can check."""
    first = build_layout(design)
    second = build_layout(design)
    assert [a.as_dict() for a in first.assignments] == \
           [a.as_dict() for a in second.assignments]

    other = design.model_copy(update={"randomisation_seed": design.randomisation_seed + 1})
    third = build_layout(other)
    assert [a.as_dict() for a in third.assignments] != \
           [a.as_dict() for a in first.assignments]
    # Same wells, different contents: the plate did not change shape.
    assert {(a.plate, a.well) for a in third.assignments} == \
           {(a.plate, a.well) for a in first.assignments}


def test_bad_designs_are_rejected():
    """All seven, each with the failure its expected.json names."""
    slipped, wrong = [], []
    for name in BAD_DESIGNS:
        declared = json.loads((BAD / f"{name}.expected.json").read_text(encoding="utf-8"))
        kwargs = {
            key: declared[key]
            for key in ("stock_mM", "transfer_uL", "max_solvent_pct")
            if key in declared
        }
        try:
            review_design(BAD / f"{name}.yaml", results_dir=RESULTS, **kwargs)
        except ReviewFailed as failure:
            if failure.failure != declared["expected_failure"]:
                wrong.append(
                    f"{name}: declared {declared['expected_failure']}, "
                    f"got {failure.failure}"
                )
        else:
            slipped.append(name)

    assert not slipped, f"bad designs that passed review: {slipped}"
    assert not wrong, "\n".join(wrong)


# Added tests, for behaviour the spec requires but does not name a test for.


def test_the_printed_design_passes_review_on_a_stronger_stock():
    """The printed design is sound apart from the stock it assumes."""
    result = review_design(DESIGN, results_dir=RESULTS, stock_mM=1000.0)
    assert result["dilution_problems"] == []
    assert result["commitment"]["margin_hours"] > 0
    # It needs four plates, which is the finding recorded in HANDOFF.md.
    assert result["plates"] == 4


def test_the_printed_design_needs_more_than_one_plate(design):
    """60 combinations plus 12 controls against 60 usable interior wells."""
    usable = design.plate_format - len(perimeter_wells(design.rows, design.columns))
    needed_for_one_replicate = design.combinations + design.controls.total
    assert needed_for_one_replicate > usable
    assert build_layout(design).plates == 4


def test_timezones_are_compared_as_instants():
    """The design carries an India Standard Time offset.

    Comparing wall clocks rather than instants would be wrong by five and a
    half hours, which is easily enough to flip the answer.
    """
    result = check_commitment_precedes_data(DESIGN, RESULTS)
    assert result["committed_at"].endswith("+00:00")
    assert result["earliest_reading"].endswith("+00:00")


def test_an_undated_reading_is_refused(tmp_path):
    """A reading with no timestamp settles nothing either way."""
    (tmp_path / "plate01.json").write_text(json.dumps({"plate": 1}), encoding="utf-8")
    with pytest.raises(CommitmentError) as caught:
        check_commitment_precedes_data(DESIGN, tmp_path)
    assert caught.value.failure == "undated_reading"


def test_this_build_imported_its_own_modules():
    import layout
    import review

    build_dir = Path(__file__).resolve().parents[1]
    for module in (layout, review):
        assert Path(module.__file__).resolve().parent == build_dir
