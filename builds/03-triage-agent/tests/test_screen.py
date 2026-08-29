"""Tests for Build 03. Nothing here touches the network.

Every record comes from the committed fixture corpus by way of the cache, and
every model reply comes from a stub. There is no code path in this file that
can reach NCBI or Anthropic, which is checked explicitly at the foot.
"""

import json
from pathlib import Path
from typing import Any

import cache
import eutils
import pytest
import screen
from agent import run_agent
from criteria import Criteria, CriteriaError, load_criteria
from models import Verdict
from prompts import ASYMMETRY, build_task
from stub_client import ScreeningClient, screen_record
from tracing import Trace

BUILD = Path(__file__).resolve().parents[1]
CORPUS = BUILD / "fixtures" / "corpus"
BROKEN = BUILD / "fixtures" / "broken_criteria"
CRITERIA_FILE = BUILD / "criteria" / "repurposing_v3.yaml"

FLAG_CASES = ["99000003", "99000004"]


@pytest.fixture
def criteria() -> Criteria:
    return load_criteria(CRITERIA_FILE)


@pytest.fixture
def gold() -> dict[str, Any]:
    return json.loads((BUILD / "fixtures" / "gold.json").read_text(encoding="utf-8"))


@pytest.fixture
def all_pmids() -> list[str]:
    return sorted(p.stem for p in CORPUS.glob("*.json"))


def read_trace(run_dir: Path, run_id: str) -> list[dict[str, Any]]:
    path = run_dir / f"{run_id}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def events(run_dir: Path, event: str) -> list[dict[str, Any]]:
    """Every event of one kind across every trace file in the directory."""
    out = []
    for path in run_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["event"] == event:
                out.append(record)
    return out


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Point the corpus at the fixtures and the loop at a stub.

    Returns a callable taking the stub client, so a test can choose how the
    model behaves without repeating the wiring.
    """

    def _wire(client):
        monkeypatch.setattr(eutils, "CACHE_DIR", CORPUS)

        def _run(task, max_steps=20, **kwargs):
            kwargs.setdefault("client", client)
            kwargs.setdefault("run_dir", str(tmp_path))
            kwargs.setdefault("backoff_s", 0.0)
            return run_agent(task, max_steps, **kwargs)

        monkeypatch.setattr(screen, "run_agent", _run)
        return tmp_path

    return _wire


# The five tests named in the spec.


def test_every_record_is_accounted_for(wired, tmp_path, criteria, all_pmids):
    """Every record leaves a verdict or a logged gap. Never nothing."""
    failing = ["99000007", "99000031", "99000052"]
    run_dir = wired(ScreeningClient(corpus_dir=CORPUS, fail_on=failing))
    trace = Trace(str(tmp_path))

    verdicts, failed = screen.screen_corpus(all_pmids, criteria, trace)

    assert len(all_pmids) == 61
    assert len(verdicts) + len(failed) == 61
    assert sorted(failed) == sorted(failing)

    # The three gaps are named in the trace, not merely absent from the output.
    recorded = read_trace(tmp_path, trace.run_id)
    gaps = [r for r in recorded if r["event"] == "record_failed"]
    assert sorted(g["pmid"] for g in gaps) == sorted(failing)
    for gap in gaps:
        assert gap["reason"] == "FAILED"
    assert run_dir == tmp_path


def test_criteria_version_on_every_verdict(wired, tmp_path, criteria, all_pmids):
    """A run screened under version 2 must never be compared with version 3."""
    wired(ScreeningClient(corpus_dir=CORPUS, criteria_version=criteria.version))
    trace = Trace(str(tmp_path))

    verdicts, failed = screen.screen_corpus(all_pmids, criteria, trace)

    assert not failed
    stamped = {v.criteria_version for v in verdicts}
    assert stamped == {criteria.version}

    # And the stamp is the version in the file on disk, not a constant that
    # drifted away from it.
    on_disk = load_criteria(CRITERIA_FILE).version
    assert stamped == {on_disk}


def test_ambiguous_records_flag_rather_than_guess(wired, tmp_path, criteria):
    """A criterion that cannot be judged is not a criterion that failed."""
    wired(ScreeningClient(corpus_dir=CORPUS))
    trace = Trace(str(tmp_path))

    verdicts, failed = screen.screen_corpus(FLAG_CASES, criteria, trace)

    assert not failed
    assert len(verdicts) == 2
    for verdict in verdicts:
        assert verdict.decision == "flag"
        assert verdict.confidence == "low"
        assert verdict.decision not in ("include", "exclude")
        # A flag names no failed criterion: nothing failed, something could
        # not be judged.
        assert verdict.criteria_failed == []


def test_criteria_file_must_validate():
    """A criteria file that does not validate halts the run.

    Both fixtures are files a careless author could produce, and neither may
    be tolerated: a run that fell back to a default would produce verdicts
    nobody could reconstruct.
    """
    with pytest.raises(CriteriaError) as missing:
        load_criteria(BROKEN / "missing_version.yaml")
    assert "version" in str(missing.value)

    with pytest.raises(CriteriaError) as unknown:
        load_criteria(BROKEN / "unknown_key.yaml")
    assert "on_ambiguty" in str(unknown.value)

    # No fallback: a missing file is a halt, not a default.
    with pytest.raises(CriteriaError):
        load_criteria(BROKEN / "does_not_exist.yaml")


def test_cache_prevents_refetch(tmp_path):
    """A second read costs nothing, which is what lets the tests run offline."""
    calls: list[str] = []
    payload = {"status": "ok", "pmid": "99000005", "title": "t", "abstract": "a"}

    def counting_fetcher(pmid: str) -> dict[str, Any]:
        calls.append(pmid)
        return payload

    first = eutils.fetch_abstract("99000005", cache_dir=tmp_path, fetcher=counting_fetcher)
    assert calls == ["99000005"]
    assert first == payload

    second = eutils.fetch_abstract("99000005", cache_dir=tmp_path, fetcher=counting_fetcher)
    assert second == payload
    # The counter did not move: the second read came from the cache.
    assert calls == ["99000005"]
    assert (tmp_path / "99000005.json").exists()


# Added tests, for behaviour the spec requires but does not name a test for.


def test_every_verdict_matches_gold(gold, all_pmids):
    """The corpus and its labels agree, record by record.

    This is the check that makes the corpus worth having. It compares the
    screening stub against gold.json for all sixty-one records, so a label
    that drifts from the record it describes fails here rather than being
    discovered by a reader.
    """
    disagreements = []
    for pmid in all_pmids:
        record = cache.read(pmid, CORPUS)
        verdict = screen_record(record, 3)
        expected = gold["labels"][pmid]
        if verdict["decision"] != expected:
            disagreements.append(f"{pmid}: gold {expected}, screened {verdict['decision']}")

    assert not disagreements, "\n".join(disagreements)


def test_designed_cases_cite_the_criterion_that_decided_them(gold):
    """A verdict that cannot say which rule decided it is not a diagnosis."""
    expected = {
        "99000001": ["liver_model"],
        "99000012": ["numeric_endpoint"],
        "99000013": ["no_drug"],
    }
    for pmid, failed in expected.items():
        verdict = screen_record(cache.read(pmid, CORPUS), 3)
        assert verdict["decision"] == "exclude"
        assert verdict["criteria_failed"] == failed
        assert gold["labels"][pmid] == "exclude"

    for pmid in ("99000002", "99000061"):
        verdict = screen_record(cache.read(pmid, CORPUS), 3)
        assert verdict["decision"] == "include"
        assert verdict["criteria_failed"] == []


def test_verdicts_validate_against_the_model(gold, all_pmids):
    """Every screened payload is a Verdict, including the reason length cap."""
    for pmid in all_pmids:
        verdict = Verdict(**screen_record(cache.read(pmid, CORPUS), 3))
        assert verdict.pmid == pmid
        assert len(verdict.reason) <= 300
        assert set(verdict.criteria_met) <= {"numeric_endpoint", "liver_model"}


def test_prompt_states_the_rule_and_the_asymmetry(criteria):
    """The instruction to flag is in the prompt, not only in the spec."""
    record = cache.read("99000003", CORPUS)
    task = build_task(record, criteria)

    assert ASYMMETRY in task
    assert "costs a paper" in task
    assert "cannot be evaluated" in task
    assert "not a criterion that failed" in task
    # The criteria are quoted, so the text judged against is the text on disk.
    for rule in criteria.include_if_all + criteria.exclude_if_any:
        assert rule.id in task
    assert str(criteria.version) in task
    assert record["abstract"] in task


def test_unparsable_reply_becomes_a_gap(wired, tmp_path, criteria):
    """A reply that is not a verdict is a gap, never a salvaged guess."""
    wired(ScreeningClient(corpus_dir=CORPUS, unparsable_on=["99000005"]))
    trace = Trace(str(tmp_path))

    verdicts, failed = screen.screen_corpus(["99000005", "99000006"], criteria, trace)

    assert failed == ["99000005"]
    assert [v.pmid for v in verdicts] == ["99000006"]
    assert any(e["reason"] == "unparsable_answer" for e in events(tmp_path, "halt"))


def test_cache_refuses_an_entry_that_does_not_match_its_hash(tmp_path):
    """A tampered cache entry is detected, not screened."""
    payload = {"status": "ok", "pmid": "99000005", "abstract": "original"}
    path = cache.write("99000005", payload, tmp_path)

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["payload"]["abstract"] = "quietly edited"
    path.write_text(json.dumps(entry), encoding="utf-8")

    with pytest.raises(cache.CacheError) as caught:
        cache.read("99000005", tmp_path)
    assert "does not match its hash" in str(caught.value)


def test_fixture_corpus_is_internally_consistent(gold, all_pmids):
    """Sixty-one records, sixty-one labels, and hashes that verify."""
    assert len(all_pmids) == 61
    assert sorted(gold["labels"]) == all_pmids
    assert gold["criteria_version"] == load_criteria(CRITERIA_FILE).version

    counts = {label: list(gold["labels"].values()).count(label) for label in
              ("include", "exclude", "flag")}
    assert counts == {"include": 9, "exclude": 50, "flag": 2}

    for pmid in all_pmids:
        # cache.read raises if the recorded hash does not match the payload.
        record = cache.read(pmid, CORPUS)
        assert record["pmid"] == pmid
        assert record["abstract"]


def test_no_test_can_reach_the_network(monkeypatch):
    """The offline guarantee, asserted rather than assumed."""

    def refuse(*args: Any, **kwargs: Any):
        raise AssertionError("a test attempted a network call")

    monkeypatch.setattr(eutils.httpx, "get", refuse)

    # A cached record is served without httpx being touched at all.
    record = eutils.fetch_abstract("99000002", cache_dir=CORPUS)
    assert record["pmid"] == "99000002"


def test_this_build_imported_its_own_modules():
    """Guards against one build being handed another build's modules."""
    build_dir = Path(__file__).resolve().parents[1]
    for module in (screen, eutils, cache):
        assert Path(module.__file__).resolve().parent == build_dir
