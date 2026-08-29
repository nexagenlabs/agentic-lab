"""Tests for Build 01. Nothing here touches the network: every model response
comes from a fixture replayed by the stub client."""

import json
from pathlib import Path
from typing import Any

import agent
from agent import dispatch, run_agent
from stub_client import StubClient, load_script


def read_trace(run_dir: Path, run_id: str) -> list[dict[str, Any]]:
    """Read one run's JSONL back, one event per line."""
    path = run_dir / f"{run_id}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def events(records: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    return [r for r in records if r["event"] == event]


# The three tests named in the spec.


def test_step_cap_marks_incomplete(tmp_path: Path) -> None:
    client = StubClient.from_fixture("step_cap")

    result = run_agent(
        "Find everything ever published on PARP inhibitors.",
        max_steps=4,
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "INCOMPLETE"
    assert result["answer"] is None
    assert result["steps"] == 4

    records = read_trace(tmp_path, result["run_id"])
    halts = events(records, "halt")
    assert len(halts) == 1
    assert halts[0]["reason"] == "step_cap"
    assert halts[0]["steps"] == 4
    assert halts[0]["max_steps"] == 4


def test_invalid_arguments_are_rejected(tmp_path: Path, monkeypatch) -> None:
    entered: list[tuple[str, int]] = []

    def spy(query: str, max_results: int) -> list[dict[str, Any]]:
        entered.append((query, max_results))
        return []

    monkeypatch.setattr(agent, "_pubmed_esearch", spy)

    negative = dispatch("search_pubmed", {"query": "olaparib", "max_results": -1})
    short = dispatch("search_pubmed", {"query": "ov", "max_results": 5})

    for result in (negative, short):
        assert result["status"] == "error"
        assert result["code"] == "invalid_arguments"

    # Validation inside the function body would not count: the body must never
    # have run at all.
    assert entered == []


def test_rejections_reach_the_trace(tmp_path: Path) -> None:
    """dispatch takes no trace, so the loop has to record the refusal.

    A rejection nobody can count is a rejection nobody will fix, which is why
    CLAUDE.md rule 5 asks for it in the trace whoever writes it there.
    """
    client = StubClient.from_fixture("malformed_arguments")

    result = run_agent(
        "Find everything on niraparib.",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )
    assert result["status"] == "COMPLETE"

    rejections = events(read_trace(tmp_path, result["run_id"]), "tool_rejected")
    assert len(rejections) == 1
    assert rejections[0]["tool"] == "search_pubmed"
    assert rejections[0]["code"] == "invalid_arguments"


def test_trace_replays_the_run(tmp_path: Path) -> None:
    script = load_script("happy_path")
    client = StubClient(script)

    result = run_agent(
        "What has been published on olaparib in ovarian carcinoma?",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )
    assert result["status"] == "COMPLETE"

    # Everything below is reconstructed from the file alone.
    records = read_trace(tmp_path, result["run_id"])

    replayed = [(r["tool"], r["args"]) for r in events(records, "tool_request")]
    expected = [(t["name"], t["input"]) for t in script["turns"] if t["kind"] == "tool_use"]
    assert replayed == expected

    outcomes = [(r["tool"], r["status"]) for r in events(records, "tool_result")]
    assert outcomes == [("search_pubmed", "ok")]

    versions = {r["model"] for r in events(records, "model_response")}
    assert versions == {script["model"]}

    halts = events(records, "halt")
    assert len(halts) == 1
    assert halts[0]["reason"] == "complete"
    assert halts[0]["steps"] == len(client.messages.calls) == 2
    assert halts[0]["max_steps"] == 20

    assert {r["run_id"] for r in records} == {result["run_id"]}
    assert all("ts" in r and "event" in r for r in records)


# Added tests, for behaviour the spec requires but does not name a test for.


def test_budget_halts_before_the_call(tmp_path: Path) -> None:
    client = StubClient.from_fixture("happy_path")

    result = run_agent(
        "What has been published on olaparib?",
        client=client,
        token_budget=100,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "INCOMPLETE"
    assert result["reason"] == "budget"
    assert result["answer"] is None
    # The first call was made, the second was stopped before it was spent.
    assert len(client.messages.calls) == 1

    halts = events(read_trace(tmp_path, result["run_id"]), "halt")
    assert halts[0]["reason"] == "budget"


def test_transient_error_is_retried_once(tmp_path: Path) -> None:
    client = StubClient.from_fixture("transient_then_success")

    result = run_agent(
        "What has been published on olaparib?",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "COMPLETE"
    assert result["answer"] == "Answered on the retry."
    # The retry took a step of its own.
    assert result["steps"] == 2

    errors = events(read_trace(tmp_path, result["run_id"]), "model_error")
    assert [e["status_code"] for e in errors] == [429]
    assert errors[0]["retrying"] is True


def test_permanent_error_is_never_retried(tmp_path: Path) -> None:
    client = StubClient.from_fixture("permanent_error")

    result = run_agent(
        "What has been published on olaparib?",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "FAILED"
    assert result["code"] == "api_error"
    assert result["answer"] is None
    assert len(client.messages.calls) == 1

    errors = events(read_trace(tmp_path, result["run_id"]), "model_error")
    assert errors[0]["status_code"] == 400
    assert errors[0]["retrying"] is False


def test_circuit_breaker_disables_a_failing_tool(tmp_path: Path) -> None:
    client = StubClient.from_fixture("tool_failure_loop")

    result = run_agent(
        "Search for anything.",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "COMPLETE"

    records = read_trace(tmp_path, result["run_id"])
    opened = events(records, "circuit_open")
    assert len(opened) == 1
    assert opened[0]["tool"] == "search_pubmed"
    assert opened[0]["failures"] == agent.FAILURE_LIMIT

    codes = [r["code"] for r in events(records, "tool_result")]
    assert codes == ["invalid_arguments"] * 3 + ["tool_disabled"]

    # Once disabled, the tool is no longer offered to the model.
    assert [t["name"] for t in client.messages.calls[-1]["tools"]] == ["save_note"]


def test_write_tool_is_blocked_without_approval(tmp_path: Path) -> None:
    client = StubClient.from_fixture("write_attempt")

    result = run_agent(
        "Record the shortlist in the notebook.",
        client=client,
        run_dir=str(tmp_path),
        backoff_s=0.0,
    )

    assert result["status"] == "COMPLETE"

    records = read_trace(tmp_path, result["run_id"])
    blocked = events(records, "tool_blocked")
    assert blocked[0]["tool"] == "save_note"
    assert blocked[0]["code"] == "awaiting_human_approval"

    # Nothing was written.
    assert not (tmp_path / "notes.jsonl").exists()
    assert not Path("notes.jsonl").exists()


def test_unknown_tool_returns_a_structured_error() -> None:
    result = dispatch("delete_everything", {})

    assert result == {
        "status": "error",
        "code": "unknown_tool",
        "tool": "delete_everything",
    }


def test_this_build_imported_its_own_modules() -> None:
    """Build 01 and Build 02 both carry an agent.py, a config.py and a
    stub_client.py. If one pytest process hands this build the other one, the
    tests above are quietly measuring the wrong code. This asserts the module
    under test came from this folder.
    """
    build_dir = Path(__file__).resolve().parents[1]
    assert Path(agent.__file__).resolve().parent == build_dir, (
        f"agent was imported from {agent.__file__}, not from {build_dir}"
    )
