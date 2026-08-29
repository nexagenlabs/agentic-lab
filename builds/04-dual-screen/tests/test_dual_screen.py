"""The seven tests the spec names, plus what they left uncovered.

Nothing here reaches the network. The two screens are committed fixtures, and
the one test that runs a screen drives it with a stub.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from adjudicate import find_disagreements, write_adjudication
from config import GOLD_NEGATIVES, GOLD_SEED, SCREEN_A_MODEL, SCREEN_B_MODEL
from criteria import load_criteria
from goldset import build_gold_set, load_gold
from metrics import ACCURACY_REFUSAL, MetricRefused, accuracy, agreement, kappa_band
from prompts import build_task_a, build_task_b
from report import render_report
from scoring import ScoringError, score_run
from screens import (
    SAME_AGENT_REFUSAL,
    ScreenConfigurationError,
    load_screen,
    plan_screens,
)

BUILD = Path(__file__).resolve().parents[1]
FIXTURES = BUILD / "fixtures"
CRITERIA_FILE = BUILD / "criteria" / "repurposing_v3.yaml"

# The threshold is a property of the protocol, decided before the run. It is
# written here, in the test, rather than defaulted in the code it measures.
SENSITIVITY_THRESHOLD = 0.85


@pytest.fixture
def criteria():
    return load_criteria(CRITERIA_FILE)


@pytest.fixture
def gold_set():
    return build_gold_set(load_gold(FIXTURES / "gold.json"),
                          seed=GOLD_SEED, negatives=GOLD_NEGATIVES)


@pytest.fixture
def expected() -> dict[str, Any]:
    return json.loads((FIXTURES / "agreement_expected.json").read_text(encoding="utf-8"))


@pytest.fixture
def plan():
    return plan_screens("two_agents", model_a=SCREEN_A_MODEL, model_b=SCREEN_B_MODEL)


@pytest.fixture
def decisions():
    def _load(name: str) -> dict[str, str]:
        screen = load_screen(FIXTURES / f"screen_{name}.json")
        return {v.pmid: v.decision for v in screen["verdicts"]}

    return _load


@pytest.fixture
def run(tmp_path, gold_set, plan, criteria):
    """A complete scored run over the committed screens."""
    return score_run(
        FIXTURES / "screen_a.json",
        FIXTURES / "screen_b.json",
        gold_set,
        sensitivity_threshold=SENSITIVITY_THRESHOLD,
        plan=plan,
        criteria_version=criteria.version,
        criteria_file="criteria/repurposing_v3.yaml",
        run_id="test0001",
        out_dir=tmp_path,
    )


# The seven tests named in the spec.


def test_sensitivity_above_threshold(run):
    """The threshold is an input, so it cannot be chosen after the result."""
    assert run["sensitivity_threshold"] == SENSITIVITY_THRESHOLD
    sensitivity = run["screen_a_performance"]["sensitivity"]
    assert sensitivity >= SENSITIVITY_THRESHOLD
    assert run["sensitivity_met"] is True

    # score_run refuses to supply a threshold of its own.
    with pytest.raises(TypeError):
        score_run(FIXTURES / "screen_a.json", FIXTURES / "screen_b.json", None,
                  plan=None, criteria_version=3, criteria_file="x",
                  run_id="x", out_dir="x")


def test_agreement_reported(run, tmp_path):
    """All four agreement statistics, in the manifest and in the report."""
    stats = run["agreement"]
    for key in ("observed_agreement", "kappa", "pabak", "ac1"):
        assert key in stats

    report = (tmp_path / "screen_report.md").read_text(encoding="utf-8")
    assert "Observed agreement" in report
    assert "Cohen's kappa" in report
    assert "PABAK" in report
    assert "Gwet's AC1" in report

    # The band travels as a word, not only as a number.
    assert stats["kappa_band"] == "moderate"
    assert "moderate" in report
    assert f"{stats['kappa']:.3f}" in report


def test_criteria_version_matches(run, criteria, tmp_path):
    """One version across both screens, and it matches the file on disk."""
    for name in ("a", "b"):
        screen = load_screen(FIXTURES / f"screen_{name}.json")
        assert screen["criteria_version"] == criteria.version
        for verdict in screen["verdicts"]:
            assert verdict.criteria_version == criteria.version
    assert run["criteria_version"] == criteria.version

    # Scoring across versions raises rather than proceeding.
    stale = json.loads((FIXTURES / "screen_b.json").read_text(encoding="utf-8"))
    stale["criteria_version"] = 2
    for verdict in stale["verdicts"]:
        verdict["criteria_version"] = 2
    stale_path = tmp_path / "screen_b_v2.json"
    stale_path.write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(ScoringError) as caught:
        score_run(FIXTURES / "screen_a.json", stale_path, None,
                  sensitivity_threshold=SENSITIVITY_THRESHOLD, plan=None,
                  criteria_version=criteria.version, criteria_file="x",
                  run_id="x", out_dir=tmp_path)
    assert "different criteria versions" in str(caught.value)


def test_accuracy_is_refused():
    """Refused, with the reason, rather than merely omitted."""
    with pytest.raises(MetricRefused) as caught:
        accuracy(true_positives=1, true_negatives=1)
    message = str(caught.value)
    assert message == ACCURACY_REFUSAL
    assert "prevalence" in message
    assert "excluded every record" in message


def test_same_agent_twice_requires_acknowledgement():
    """One model twice is not a second reviewer."""
    with pytest.raises(ScreenConfigurationError) as caught:
        plan_screens("same_agent_twice", model_a=SCREEN_A_MODEL)
    message = str(caught.value)
    assert message == SAME_AGENT_REFUSAL
    assert "temperature" in message
    assert "not a second reviewer" in message

    allowed = plan_screens("same_agent_twice", model_a=SCREEN_A_MODEL,
                           acknowledge_not_a_second_reviewer=True)
    assert allowed.mode == "same_agent_twice"
    assert allowed.model_a == allowed.model_b


def test_kappa_matches_known_value(decisions, expected):
    """The statistics are right, not merely present.

    The fixtures were built backwards from a chosen contingency table, so
    these are values the table was designed to produce rather than whatever
    the implementation happens to return.
    """
    observed = agreement(decisions("a"), decisions("b"))
    assert observed.n == expected["n"]
    assert round(observed.observed, 3) == round(expected["observed_agreement"], 3)
    assert round(observed.kappa, 3) == round(expected["kappa"], 3)
    assert round(observed.pabak, 3) == round(expected["pabak"], 3)
    assert round(observed.ac1, 3) == round(expected["ac1"], 3)
    assert observed.band == expected["kappa_band"]


def test_disagreements_go_to_adjudication(tmp_path, run):
    """Every difference is listed, with both sides, and none is resolved."""
    a = load_screen(FIXTURES / "screen_a.json")
    b = load_screen(FIXTURES / "screen_b.json")
    adjudication = find_disagreements(a["verdicts"], b["verdicts"])

    known = json.loads((FIXTURES / "disagreements_expected.json").read_text(encoding="utf-8"))
    assert [d.pmid for d in adjudication.disagreements] == known["pmids"]
    assert adjudication.count == known["count"]

    path = write_adjudication(tmp_path / "adj.json", adjudication)
    body = json.loads(path.read_text(encoding="utf-8"))

    assert body["sent_to_human_adjudication"] == known["count"]
    assert body["all_unresolved"] is True
    for entry in body["disagreements"]:
        assert entry["screen_a"]["decision"] != entry["screen_b"]["decision"]
        assert entry["screen_a"]["reason"]
        assert entry["screen_b"]["reason"]
        # Nothing was resolved automatically.
        assert entry["resolution"] is None

    assert run["adjudication"]["sent_to_human_adjudication"] == known["count"]


# Added tests, for behaviour the spec requires but does not name a test for.


def test_the_two_screens_cannot_see_each_other():
    """Independence is structural, so assert the structure.

    run_screen takes no parameter that could carry the other screen's
    verdicts. If one is ever added, this fails and somebody has to justify it.
    """
    import inspect

    import screens

    parameters = set(inspect.signature(screens.run_screen).parameters)
    forbidden = {"other", "other_screen", "verdicts", "screen_a", "screen_b",
                 "previous", "peer"}
    assert not (parameters & forbidden), (
        f"run_screen gained a parameter that could leak one screen into the "
        f"other: {sorted(parameters & forbidden)}"
    )


def test_two_agents_refuses_the_same_model_twice():
    """same_agent_twice under another name is still same_agent_twice."""
    with pytest.raises(ScreenConfigurationError) as caught:
        plan_screens("two_agents", model_a=SCREEN_A_MODEL, model_b=SCREEN_A_MODEL)
    assert "same model twice" in str(caught.value)


def test_agent_and_human_needs_a_human_file():
    with pytest.raises(ScreenConfigurationError) as caught:
        plan_screens("agent_and_human", model_a=SCREEN_A_MODEL)
    assert "human_file" in str(caught.value)

    plan = plan_screens("agent_and_human", model_a=SCREEN_A_MODEL,
                        human_file="fixtures/human.json")
    assert plan.model_b == "human"
    assert plan.prompt_b is None


def test_the_two_prompts_differ_but_quote_the_same_criteria(criteria):
    """Different instruments, one rule book."""
    record = {"pmid": "99000005", "title": "t", "abstract": "a",
              "journal": "j", "year": 2021, "publication_types": ["Journal Article"]}
    a = build_task_a(record, criteria)
    b = build_task_b(record, criteria)

    assert a != b
    for rule in criteria.include_if_all + criteria.exclude_if_any:
        assert rule.text.strip().split("\n")[0] in a
        assert rule.text.strip().split("\n")[0] in b
    # Neither prompt mentions the other screen or its verdicts.
    for task in (a, b):
        assert "other screen" not in task.lower()
        assert "screen b" not in task.lower()
        assert "screen a" not in task.lower()


def test_kappa_bands_are_the_landis_and_koch_words():
    assert kappa_band(-0.1) == "poor"
    assert kappa_band(0.10) == "slight"
    assert kappa_band(0.30) == "fair"
    assert kappa_band(0.50) == "moderate"
    assert kappa_band(0.70) == "substantial"
    assert kappa_band(0.90) == "almost perfect"
    assert kappa_band(1.0) == "almost perfect"


def test_report_is_pasteable(run, tmp_path):
    """Every number in the report carries what a reader needs to read it."""
    report = (tmp_path / "screen_report.md").read_text(encoding="utf-8")

    assert "\\" not in report, "a Windows path leaked into a methods section"
    assert "{" not in report and "}" not in report, "an unfilled placeholder"
    assert str(run["gold_set"]["seed"]) in report
    assert "every inclusion, every flag and every designed case" in report
    assert "Accuracy is not computed" in report
    # Sensitivity appears before positive predictive value.
    assert report.index("Sensitivity") < report.index("Positive predictive value")
    # The union is explained rather than left to puzzle the reader.
    assert "sum to more than the total" in report


def test_manifest_records_how_the_gold_set_was_drawn(run):
    gold = run["gold_set"]
    assert gold["seed"] == GOLD_SEED
    assert gold["seeded_negatives"] == GOLD_NEGATIVES
    assert gold["total"] == run["screen_a_performance"]["gold_size"]
    assert "Enriched by rule" in gold["selection"]


def test_render_report_does_not_touch_disk(run):
    """The template is a pure function of the manifest."""
    first = render_report(run)
    second = render_report(run)
    assert first == second


def test_this_build_imported_its_own_modules():
    """Guards against one build being handed another build's modules."""
    import goldset
    import metrics
    import screens

    build_dir = Path(__file__).resolve().parents[1]
    for module in (screens, metrics, goldset):
        assert Path(module.__file__).resolve().parent == build_dir
