"""Tests for the gold set rule.

The rule is the thing under test, never the number it currently produces.
Every assertion here derives its expectation from the ground truth file, so
that adding a record to the corpus changes the gold set and does not break
these tests, which is the whole point of writing the rule as code.
"""

import json
from pathlib import Path

import pytest
from config import GOLD_NEGATIVES, GOLD_SEED
from goldset import GoldSetError, build_gold_set, load_gold

BUILD = Path(__file__).resolve().parents[1]
GOLD_FILE = BUILD / "fixtures" / "gold.json"


@pytest.fixture
def gold() -> dict:
    return load_gold(GOLD_FILE)


@pytest.fixture
def gold_set(gold):
    return build_gold_set(gold, seed=GOLD_SEED, negatives=GOLD_NEGATIVES)


def test_every_inclusion_flag_and_designed_case_is_present(gold, gold_set):
    """The rule, asserted against the ground truth rather than a list."""
    expected_inclusions = {p for p, label in gold["labels"].items() if label == "include"}
    expected_flags = {p for p, label in gold["labels"].items() if label == "flag"}
    expected_designed = set(gold["notes"])

    selected = set(gold_set.pmids)
    assert expected_inclusions <= selected
    assert expected_flags <= selected
    assert expected_designed <= selected


def test_the_set_is_a_union_with_no_double_counting(gold, gold_set):
    """99000002 and 99000061 are designed cases and also inclusions.

    A set built by concatenation would list them twice and inflate every
    denominator that follows. This asserts the union rather than trusting the
    construction that produced it.
    """
    both = set(gold_set.inclusions) & set(gold_set.designed)
    assert both, "the corpus should contain a record that is both, or this proves nothing"

    assert len(gold_set.pmids) == len(set(gold_set.pmids))
    for pmid in both:
        assert gold_set.pmids.count(pmid) == 1

    # The itemised counts overlap by exactly the number of shared records, and
    # the composition says so rather than leaving the arithmetic puzzling.
    composition = gold_set.composition()
    naive_total = (
        composition["inclusions"]
        + composition["flags"]
        + composition["designed_cases"]
        + composition["seeded_negatives"]
    )
    assert naive_total - composition["designed_also_counted_elsewhere"] == gold_set.size


def test_size_follows_the_corpus_rather_than_a_constant(gold, gold_set):
    """The size is an output. Derived here, never hard-coded."""
    labels = gold["labels"]
    enriched = {p for p, label in labels.items() if label in ("include", "flag")}
    enriched |= set(gold["notes"])
    assert gold_set.size == len(enriched) + GOLD_NEGATIVES
    assert gold_set.corpus_size == len(labels)


def test_seeded_negatives_are_drawn_from_outside_the_enriched_categories(gold_set):
    """A negative that is also a designed case would be selected twice over."""
    enriched = set(gold_set.inclusions) | set(gold_set.flags) | set(gold_set.designed)
    for pmid in gold_set.seeded_negatives:
        assert pmid not in enriched
        assert gold_set.labels[pmid] == "exclude"
    assert len(gold_set.seeded_negatives) == GOLD_NEGATIVES


def test_the_draw_is_reproducible_from_its_seed(gold):
    """A gold set that cannot be reconstructed is not a reference standard."""
    first = build_gold_set(gold, seed=GOLD_SEED, negatives=GOLD_NEGATIVES)
    second = build_gold_set(gold, seed=GOLD_SEED, negatives=GOLD_NEGATIVES)
    assert first.seeded_negatives == second.seeded_negatives
    assert first.pmids == second.pmids

    other = build_gold_set(gold, seed=GOLD_SEED + 1, negatives=GOLD_NEGATIVES)
    assert other.seeded_negatives != first.seeded_negatives
    # The enriched part does not move with the seed. Only the negatives do.
    assert other.inclusions == first.inclusions
    assert other.designed == first.designed


def test_the_seed_must_be_supplied(gold):
    """Required, not defaulted: a seed nobody passes is a seed nobody records."""
    with pytest.raises(TypeError):
        build_gold_set(gold, negatives=GOLD_NEGATIVES)


def test_a_corpus_with_no_inclusions_is_refused(gold):
    """Enrichment exists to guarantee positives. No positives, no gold set."""
    barren = {
        "criteria_version": gold["criteria_version"],
        "labels": {p: "exclude" for p in gold["labels"]},
        "notes": {},
    }
    with pytest.raises(GoldSetError) as caught:
        build_gold_set(barren, seed=GOLD_SEED, negatives=GOLD_NEGATIVES)
    assert "no inclusions" in str(caught.value)


def test_too_few_negatives_is_refused(gold):
    """Asking for more negatives than the corpus can spare is an error."""
    with pytest.raises(GoldSetError) as caught:
        build_gold_set(gold, seed=GOLD_SEED, negatives=10_000)
    assert "cannot draw" in str(caught.value)


def test_a_designed_case_without_a_label_is_refused(gold):
    """Ground truth that describes a record it does not label is incoherent."""
    broken = json.loads(json.dumps(gold))
    broken["notes"]["99999999"] = "a designed case that is not in the corpus"
    with pytest.raises(GoldSetError) as caught:
        build_gold_set(broken, seed=GOLD_SEED, negatives=GOLD_NEGATIVES)
    assert "99999999" in str(caught.value)


def test_composition_records_how_the_set_was_selected(gold_set):
    """A reader must see enrichment rather than infer it."""
    composition = gold_set.composition()
    assert composition["seed"] == GOLD_SEED
    assert composition["total"] == gold_set.size
    assert "Enriched by rule" in composition["selection"]
    assert composition["corpus_size"] > composition["total"]
