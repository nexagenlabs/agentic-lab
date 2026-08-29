"""Tests for Build 08. Nothing here reaches the network, and nothing here
requires AutoDock Vina to be installed.

Every docking call goes through ``RecordedEngine``, which replays output
captured under ``fixtures/vina_output/``. The coordinates in those files are
fabricated but they are real geometry: the redocking RMSD and the cluster
occupancy asserted below are computed from them rather than stored beside
them, so a fixture that made the controls easy would show up as a suspicious
number rather than as a passing test.
"""

import json
from pathlib import Path

import pytest
from affinity import AFFINITY_METHODS, AffinityClaimRefused
from campaign import (
    SCORE_TOLERANCE,
    rerun_from_manifest,
    run_campaign,
    scores_agree,
)
from comparison import ComparisonSetRefused, build_comparison_set
from controls import decoy_enrichment, redocking_control
from engine import EngineError, RecordedEngine, VinaEngine
from geometry import cluster_occupancy, rmsd, spread
from models import (
    DockingBox,
    DockingResult,
    Pose,
    PreparationDecisions,
    StructureRecord,
)
from parse import parse_poses
from pydantic import ValidationError
from rank import RankingRefused, consensus_rank, enrichment_factor, rank_results

BUILD = Path(__file__).resolve().parents[1]
FIX = BUILD / "fixtures"
OUTPUT = FIX / "vina_output"

SEED = 20260829
EXHAUSTIVENESS = 16

# Passed in, never defaulted. Two angstroms is the redocking convention and
# an enrichment factor of two at ten per cent is a modest ask; both are stated
# here where a reader can disagree with them.
REDOCK_THRESHOLD_ANGSTROM = 2.0
ENRICHMENT_FRACTION = 0.1
ENRICHMENT_THRESHOLD = 2.0


@pytest.fixture
def engine():
    return RecordedEngine(recordings=OUTPUT)


@pytest.fixture
def records():
    out = {}
    for path in sorted((FIX / "structures").glob("*.json")):
        record = StructureRecord(**json.loads(path.read_text(encoding="utf-8")))
        out[record.target] = record
    return out


@pytest.fixture
def preparation():
    return PreparationDecisions(
        assay_ph=7.4,
        protonation_state="Asp of the catalytic dyad protonated at pH 7.4",
        crystallographic_waters="selected",
        waters_retained=["HOH 412", "HOH 517"],
        metals_and_cofactors="one magnesium ion retained, no cofactor present",
        ligand_tautomer="the 4-oxo tautomer, which dominates in water",
    )


def box(target: str, strategy: str = "explicit", set_id: str = "SET-KIN-01"):
    return DockingBox(
        strategy=strategy,
        centre_xyz=(18.40, -4.25, 31.10),
        size_xyz=(22.0, 22.0, 22.0),
        defining_residues=["LEU101", "VAL118"] if strategy == "residue_list" else None,
        justification=(
            "Centred on the co-crystallised ligand of KIN-ALPHA and applied "
            "unchanged to every target in the set, so the boxes are the same "
            "question asked four times."
        ),
        comparison_set_id=set_id,
    )


def dock_one(engine, target: str, ligand: str) -> DockingResult:
    output = engine.dock(target, ligand, box(target), seed=SEED,
                         exhaustiveness=EXHAUSTIVENESS)
    return DockingResult(
        ligand_id=ligand, target=target, poses=parse_poses(output),
        seed=SEED, exhaustiveness=EXHAUSTIVENESS, engine=engine.name,
    )


# The seven tests named in the spec.


def test_redocking_control_recovers_pose(engine):
    """If the setup cannot recover a known answer, nothing else it says
    about an unknown compound is worth reading."""
    known = json.loads((FIX / "redock" / "crystal_pose.json").read_text(
        encoding="utf-8"))
    crystal = [tuple(atom) for atom in known["coordinates"]]

    result = dock_one(engine, known["target"], known["ligand_id"])
    control = redocking_control(result, crystal,
                               threshold_angstrom=REDOCK_THRESHOLD_ANGSTROM)

    assert control.passed, (
        f"redock recovered the pose to {control.top_pose_rmsd:.2f} angstroms, "
        f"outside the {REDOCK_THRESHOLD_ANGSTROM} angstrom threshold"
    )
    assert control.top_pose_rmsd == pytest.approx(1.13, abs=0.01)
    # The pose that scored best is also the pose closest to the crystal one,
    # which is the case where the score and the geometry agree. Where they do
    # not, the control is what tells you.
    assert control.best_pose_rank == 1


def test_decoy_enrichment_exceeds_threshold(engine):
    """Enrichment is the claim docking supports, so it is what gets measured."""
    library = json.loads((FIX / "decoys" / "library.json").read_text(
        encoding="utf-8"))
    actives = {c["ligand_id"] for c in library["compounds"] if c["active"]}
    results = [dock_one(engine, library["target"], c["ligand_id"])
               for c in library["compounds"]]

    control = decoy_enrichment(results, actives,
                               fraction=ENRICHMENT_FRACTION,
                               threshold=ENRICHMENT_THRESHOLD)

    assert control.actives == 8
    assert control.decoys == 40
    assert control.passed, (
        f"enrichment factor {control.factor:.2f} at "
        f"{ENRICHMENT_FRACTION:.0%} did not clear {ENRICHMENT_THRESHOLD}"
    )
    assert control.factor == pytest.approx(3.6, abs=0.01)

    # And the library is not rigged: a decoy outscores every active in it.
    ordered = sorted(((r.ligand_id, r.top_score) for r in results),
                     key=lambda item: item[1])
    assert ordered[0][0] not in actives, (
        "the best scoring compound in the library is an active, which makes "
        "this an easier screen than any real one"
    )


def test_ranking_rejects_mixed_provenance(engine, records, preparation):
    """Chapter 2's failure, fixed structurally rather than by remembering."""
    experimental = dock_one(engine, "KIN-ALPHA", "LIG-PROBE")
    predicted = dock_one(engine, "KIN-DELTA", "LIG-PROBE")

    with pytest.raises(RankingRefused) as caught:
        rank_results([experimental, predicted], records)
    assert caught.value.code == "mixed_provenance"
    assert "twenty-two targets" in caught.value.detail
    assert caught.value.as_dict()["status"] == "REFUSED"

    # Only with the flag, and the flag reaches the manifest.
    ranking = rank_results([experimental, predicted], records,
                           allow_mixed_provenance=True)
    assert [entry.source for entry in ranking] == ["PREDICTED", "EXPERIMENTAL"]

    pairs = [("KIN-ALPHA", "LIG-PROBE"), ("KIN-DELTA", "LIG-PROBE")]
    comparison = build_comparison_set(
        "SET-KIN-01", {target: box(target) for target, _ in pairs})
    campaign = run_campaign(pairs, comparison, records, preparation, engine,
                            seed=SEED, exhaustiveness=EXHAUSTIVENESS,
                            allow_mixed_provenance=True)
    assert campaign.manifest.allow_mixed_provenance is True
    assert "allow_mixed_provenance" in campaign.manifest.model_dump_json()

    # A set that was not flagged is refused at campaign level too.
    with pytest.raises(RankingRefused):
        run_campaign(pairs, comparison, records, preparation, engine,
                     seed=SEED, exhaustiveness=EXHAUSTIVENESS)


def test_comparison_set_enforces_one_box_strategy():
    """Four isoforms, four boxes, four days, and numbers nobody can compare."""
    boxes = {
        "KIN-ALPHA": box("KIN-ALPHA", "cocrystal_ligand"),
        "KIN-BETA": box("KIN-BETA", "cocrystal_ligand"),
    }
    consistent = build_comparison_set("SET-KIN-01", boxes)
    assert consistent.strategy == "cocrystal_ligand"

    boxes["KIN-GAMMA"] = box("KIN-GAMMA", "residue_list")
    with pytest.raises(ComparisonSetRefused) as caught:
        build_comparison_set("SET-KIN-01", boxes)
    assert caught.value.code == "mixed_box_strategies"
    assert "not the same question asked" in caught.value.detail

    # A box belonging to another comparison is refused as well, because that
    # is the same mistake arriving from the other direction.
    with pytest.raises(ComparisonSetRefused) as caught:
        build_comparison_set(
            "SET-KIN-02", {"KIN-ALPHA": box("KIN-ALPHA", "cocrystal_ligand")})
    assert caught.value.code == "wrong_comparison_set"


def test_run_is_reproducible_from_manifest(engine, records, preparation):
    """Re-run from the manifest alone, and nothing else."""
    pairs = [("KIN-ALPHA", "LIG-PROBE"), ("KIN-BETA", "LIG-PROBE")]
    comparison = build_comparison_set(
        "SET-KIN-01", {target: box(target) for target, _ in pairs})
    campaign = run_campaign(pairs, comparison, records, preparation, engine,
                            seed=SEED, exhaustiveness=EXHAUSTIVENESS)

    # Round trip through JSON, so the re-run reads what would be on disk.
    manifest = campaign.manifest.model_validate_json(
        campaign.manifest.model_dump_json())
    assert manifest.seed == SEED
    assert manifest.exhaustiveness == EXHAUSTIVENESS
    assert manifest.preparation.crystallographic_waters == "selected"

    again = rerun_from_manifest(manifest, RecordedEngine(recordings=OUTPUT))
    assert scores_agree(campaign.results, again, SCORE_TOLERANCE) == []


def test_affinity_prediction_is_refused():
    """Refusing is stronger than omitting, as with accuracy in Build 04."""
    for method in AFFINITY_METHODS:
        with pytest.raises(AffinityClaimRefused) as caught:
            method(-9.4)
        message = str(caught.value)
        assert "0.10 to 0.38" in message
        assert "minus 0.18" in message
        assert "1.5 to 2.0 log units" in message
        assert caught.value.as_dict()["status"] == "REFUSED"


def test_pose_distribution_is_retained(engine):
    """A top score from one outlier is not the evidence a cluster is.

    The two fixtures carry the same top score on purpose. Anything that
    reduces a run to the number a ranking uses cannot tell them apart, and
    that is the point: the difference exists only in the distribution.
    """
    tight = dock_one(engine, "KIN-BETA", "LIG-CLUSTER")
    scattered = dock_one(engine, "KIN-BETA", "LIG-OUTLIER")

    assert tight.top_score == scattered.top_score == -9.4
    assert len(tight.poses) == len(scattered.poses) == 8

    assert cluster_occupancy(tight.poses) == 8
    assert cluster_occupancy(scattered.poses) == 1
    assert spread(tight.poses) < 2.0
    assert spread(scattered.poses) > 20.0

    # Every pose kept, coordinates included. Without them there is no
    # distribution to look at.
    for pose in tight.poses + scattered.poses:
        assert len(pose.coordinates) == 8


# Added tests, for behaviour the spec requires but does not name a test for.


def test_preparation_decisions_have_no_defaults():
    """Undeclared defaults are how two runs of one protocol diverge."""
    complete = {
        "assay_ph": 7.4,
        "protonation_state": "neutral at pH 7.4",
        "crystallographic_waters": "removed",
        "metals_and_cofactors": "no metal, no cofactor",
        "ligand_tautomer": "the 4-oxo tautomer",
    }
    PreparationDecisions(**complete)

    for field in complete:
        missing = {k: v for k, v in complete.items() if k != field}
        with pytest.raises(ValidationError):
            PreparationDecisions(**missing)

    # Waters kept selectively have to be named.
    with pytest.raises(ValidationError) as caught:
        PreparationDecisions(**{**complete, "crystallographic_waters": "selected"})
    assert "not a protocol" in str(caught.value)


def test_a_predicted_structure_must_carry_pocket_confidence():
    """Global confidence is not the number that misleads you."""
    base = {
        "target": "KIN-OMEGA", "source": "PREDICTED", "identifier": "MOD-9XX9",
        "method": "AF3", "resolution_angstrom": None,
        "ligand_state": "unknown", "cocrystal_ligand": None,
        "prediction_confidence": None,
        "retrieved_at": "2026-02-11T09:00:00+00:00",
    }
    with pytest.raises(ValidationError) as caught:
        StructureRecord(**base)
    assert "mean pLDDT over the pocket" in str(caught.value)

    StructureRecord(**{**base, "prediction_confidence": 88.0})

    # And an experimental structure carrying one is refused the other way.
    with pytest.raises(ValidationError):
        StructureRecord(**{**base, "source": "EXPERIMENTAL",
                           "prediction_confidence": 88.0})


def test_the_apo_and_holo_distinction_is_recorded(records):
    """It dominates screening performance, so it is a field, not a note."""
    assert records["KIN-ALPHA"].ligand_state == "holo"
    assert records["KIN-ALPHA"].cocrystal_ligand == "LIG-CRYSTAL"
    assert records["KIN-GAMMA"].ligand_state == "apo"
    assert {r.ligand_state for r in records.values()} >= {"holo", "apo"}

    # Two predicted structures with very different pocket confidence, which is
    # the comparison the field exists to make possible.
    assert records["KIN-DELTA"].prediction_confidence > 90
    assert records["KIN-EPSILON"].prediction_confidence < 70


def test_consensus_is_supported_and_honestly_limited():
    """It reduces the variance of a ranking. It does not make an affinity."""
    rankings = {
        "vina": ["ACT-001", "DEC-004", "ACT-002", "DEC-009"],
        "other": ["ACT-002", "ACT-001", "DEC-009", "DEC-004"],
    }
    order = [ligand for ligand, _ in consensus_rank(rankings)]
    assert order[:2] == ["ACT-001", "ACT-002"]

    with pytest.raises(RankingRefused) as caught:
        consensus_rank({"vina": ["ACT-001"]})
    assert caught.value.code == "consensus_of_one"

    doc = consensus_rank.__doc__
    assert "does not turn a ranking into an affinity" in doc
    assert "0.10 to 0.38" in doc


def test_the_enrichment_fraction_is_not_defaulted():
    """One per cent and ten per cent are different claims."""
    scored = [("ACT-001", -9.5), ("DEC-001", -8.0), ("DEC-002", -7.0)]
    # A third of three compounds is one compound, and the one active is
    # in it, so the enrichment is three times the base rate.
    assert enrichment_factor(scored, {"ACT-001"}, 0.33) == pytest.approx(3.0)
    # A larger slice is a weaker claim, from the same numbers.
    assert enrichment_factor(scored, {"ACT-001"}, 0.5) == pytest.approx(1.5)
    with pytest.raises(RankingRefused):
        enrichment_factor(scored, set(), 0.1)
    with pytest.raises(RankingRefused):
        enrichment_factor(scored, {"ACT-001"}, 1.5)


def test_the_engine_is_not_required_to_be_installed(tmp_path):
    """The gate runs the recording. The reader runs the subprocess."""
    absent = VinaEngine(binary="vina-that-is-not-installed")
    with pytest.raises(EngineError) as caught:
        absent.dock("KIN-ALPHA", "LIG-PROBE", box("KIN-ALPHA"),
                    seed=SEED, exhaustiveness=EXHAUSTIVENESS)
    assert caught.value.code == "engine_not_installed"

    # And a recording that does not exist is an error, not a silent zero.
    empty = RecordedEngine(recordings=tmp_path)
    with pytest.raises(EngineError) as caught:
        empty.dock("KIN-ALPHA", "LIG-PROBE", box("KIN-ALPHA"),
                   seed=SEED, exhaustiveness=EXHAUSTIVENESS)
    assert caught.value.code == "no_recording"


def test_the_seed_and_exhaustiveness_reach_the_engine(engine, records,
                                                      preparation):
    """Search is stochastic. A run you cannot replay is not a run."""
    pairs = [("KIN-ALPHA", "LIG-PROBE")]
    comparison = build_comparison_set("SET-KIN-01", {"KIN-ALPHA": box("KIN-ALPHA")})
    run_campaign(pairs, comparison, records, preparation, engine,
                 seed=SEED, exhaustiveness=EXHAUSTIVENESS)
    assert engine.calls == [{
        "target": "KIN-ALPHA", "ligand_id": "LIG-PROBE", "seed": SEED,
        "exhaustiveness": EXHAUSTIVENESS, "comparison_set_id": "SET-KIN-01",
    }]


def test_rmsd_refuses_two_different_molecules():
    """An RMSD between unequal atom counts is a number with no meaning."""
    from geometry import GeometryError

    with pytest.raises(GeometryError) as caught:
        rmsd([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    assert caught.value.code == "atom_count_mismatch"

    assert rmsd([(0.0, 0.0, 0.0)], [(3.0, 4.0, 0.0)]) == pytest.approx(5.0)


def test_a_pose_without_a_score_is_refused():
    """A geometry with no score is not a pose the ranking can use."""
    from parse import ParseError

    text = "MODEL 1\nATOM      1 C1   LIG A   1       0.000   0.000   0.000\nENDMDL\n"
    with pytest.raises(ParseError) as caught:
        parse_poses(text)
    assert caught.value.code == "no_score"


def test_the_trace_is_jsonl(engine, records, preparation, tmp_path):
    """One event per line, from the first version."""
    import tracing

    trace = tracing.Trace(run_dir=tmp_path / "runs")
    pairs = [("KIN-ALPHA", "LIG-PROBE"), ("KIN-BETA", "LIG-PROBE")]
    comparison = build_comparison_set(
        "SET-KIN-01", {target: box(target) for target, _ in pairs})
    run_campaign(pairs, comparison, records, preparation, engine, seed=SEED,
                 exhaustiveness=EXHAUSTIVENESS, trace=trace)

    events = [json.loads(line) for line in
              trace.path.read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in events] == [
        "campaign_started", "docked", "docked", "campaign_complete",
    ]
    assert events[0]["seed"] == SEED
    assert events[1]["poses"] == 3


def test_a_score_is_never_presented_as_an_affinity(engine, records):
    """No field, property or key anywhere calls a score an affinity."""
    result = dock_one(engine, "KIN-ALPHA", "LIG-PROBE")
    # Field names, not the serialised values: a target called KIN-ALPHA
    # contains the letters of Ki and means nothing by it.
    names = set(DockingResult.model_fields) | set(Pose.model_fields)
    for word in ("affinity", "kd", "ki", "kcal", "energy", "potency"):
        assert not any(word in name.lower() for name in names)

    assert isinstance(result.top, Pose)
    assert result.top_score == min(pose.score for pose in result.poses)


def test_this_build_imported_its_own_modules():
    import campaign
    import geometry

    build_dir = Path(__file__).resolve().parents[1]
    for module in (campaign, geometry):
        assert Path(module.__file__).resolve().parent == build_dir
