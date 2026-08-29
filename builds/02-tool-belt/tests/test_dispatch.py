"""Tests for Build 02. Nothing here touches the network: the one test that
runs the loop drives it with a fixture replayed by the stub client."""

import json
from pathlib import Path
from typing import Any

import dispatch as dispatch_module
import pytest
from agent import run_agent
from dispatch import DESCRIPTIONS, SCHEMAS, TOOLS, dispatch
from stub_client import StubClient
from tracing import Trace


def read_trace(run_dir: Path, run_id: str) -> list[dict[str, Any]]:
    """Read one run back, one event per line."""
    path = run_dir / f"{run_id}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def events(records: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    return [r for r in records if r["event"] == event]


# The four tests named in the spec.


def test_schema_rejects_before_function_body(tmp_path: Path, monkeypatch) -> None:
    """A malformed call must never reach the function it names."""
    entered: list[dict[str, Any]] = []

    def explode(**kwargs: Any) -> dict:
        entered.append(kwargs)
        raise AssertionError("the function body was entered")

    monkeypatch.setitem(dispatch_module.REGISTRY, "search_pubmed", explode)
    trace = Trace(str(tmp_path))

    # Too short for min_length=3, and out of range for le=200.
    short = dispatch("search_pubmed", {"query": "ov"}, trace)
    oversized = dispatch("search_pubmed", {"query": "olaparib", "max_results": 500}, trace)

    for result in (short, oversized):
        assert result["status"] == "error"
        assert result["code"] == "invalid_arguments"
        assert result["detail"]

    # Validation inside the body would not count: the body never ran at all.
    assert entered == []


def test_rejection_is_logged_to_trace(tmp_path: Path) -> None:
    """A rejection nobody can count is a rejection nobody will fix."""
    trace = Trace(str(tmp_path))

    dispatch("search_pubmed", {"query": "ov"}, trace)

    rejections = events(read_trace(tmp_path, trace.run_id), "tool_rejected")
    assert len(rejections) == 1
    assert rejections[0]["tool"] == "search_pubmed"
    assert rejections[0]["errors"] >= 1


def test_declaration_matches_schema() -> None:
    """The declaration the model is shown is generated from the model that
    enforces it, so the two cannot drift apart."""
    assert TOOLS, "no tools were declared"
    for declaration in TOOLS:
        schema = SCHEMAS[declaration["name"]]
        assert declaration["input_schema"] == schema.model_json_schema()


def test_two_tools_are_distinguishable() -> None:
    """One tool cannot be misrouted. Two can, so the descriptions must say
    what each is not for."""
    names = {declaration["name"] for declaration in TOOLS}
    assert {"search_pubmed", "fetch_abstract"} <= names

    descriptions = [d["description"] for d in TOOLS]
    for description in descriptions:
        assert "Do NOT" in description

    first, second = descriptions[0], descriptions[1]
    assert first not in second
    assert second not in first


# Added tests, for behaviour the spec requires but does not name a test for.


def test_unknown_tool_returns_a_structured_error(tmp_path: Path) -> None:
    trace = Trace(str(tmp_path))
    result = dispatch("delete_everything", {}, trace)

    assert result == {
        "status": "error",
        "code": "unknown_tool",
        "tool": "delete_everything",
    }


def test_valid_call_reaches_the_function(tmp_path: Path) -> None:
    """The gate has to let good calls through, with defaults applied."""
    trace = Trace(str(tmp_path))
    result = dispatch("search_pubmed", {"query": "olaparib ovarian"}, trace)

    assert result["status"] == "ok"
    assert result["count"] == len(result["pmids"])


def test_pmid_pattern_is_enforced(tmp_path: Path) -> None:
    """fetch_abstract takes an identifier, not a search phrase."""
    trace = Trace(str(tmp_path))

    rejected = dispatch("fetch_abstract", {"pmid": "olaparib"}, trace)
    assert rejected["code"] == "invalid_arguments"

    found = dispatch("fetch_abstract", {"pmid": "31562799"}, trace)
    assert found["status"] == "ok"
    assert found["pmid"] == "31562799"


def test_every_description_names_the_other_tool() -> None:
    """The Table 2.3 pattern: the negative case points somewhere by name."""
    assert "fetch_abstract" in DESCRIPTIONS["search_pubmed"]
    assert "search_pubmed" in DESCRIPTIONS["fetch_abstract"]


def test_loop_runs_offline(tmp_path: Path) -> None:
    """The loop still works over the new boundary, with no network."""
    client = StubClient.from_fixture("happy_path")

    result = run_agent(
        "What has been published on olaparib in ovarian carcinoma?",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "COMPLETE"
    assert result["steps"] == 2

    records = read_trace(tmp_path, result["run_id"])
    assert [r["status"] for r in events(records, "tool_result")] == ["ok"]
    assert events(records, "halt")[0]["reason"] == "complete"


def test_no_api_key_is_needed(monkeypatch) -> None:
    """A reader without a key must still be able to run the tests."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = StubClient.from_fixture("happy_path")

    with pytest.raises(Exception) as caught:
        # The stub script holds two turns, so a third call would exhaust it.
        # This asserts nothing reaches the network before that point.
        for _ in range(3):
            client.messages.create(model="stub", max_tokens=1, messages=[])

    assert "script ran out" in str(caught.value)


def test_this_build_imported_its_own_modules() -> None:
    """Build 01 and Build 02 both carry an agent.py, a config.py and a
    stub_client.py. If one pytest process hands this build the other one, the
    loop test above is quietly measuring the wrong code and still passing.
    This asserts the modules under test came from this folder.
    """
    import agent as agent_module

    build_dir = Path(__file__).resolve().parents[1]
    for module in (agent_module, dispatch_module):
        assert Path(module.__file__).resolve().parent == build_dir, (
            f"{module.__name__} was imported from {module.__file__}, "
            f"not from {build_dir}"
        )
