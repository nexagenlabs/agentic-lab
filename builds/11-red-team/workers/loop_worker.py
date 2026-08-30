"""Build 01, the raw loop, in its own process.

The job carries a stub script in Build 01's own fixture format, so the loop is
driven exactly as its tests drive it. The checks are the four orchestration
decisions the build actually makes, read from the returned dict and from the
trace it wrote:

    step_cap        the cap was reached, and the run returned INCOMPLETE with
                    answer None rather than summarising partial work
    token_budget    the budget was exhausted before the cap
    tool_disabled   a tool failed three times consecutively and was withdrawn
    write_gate      a write was refused for want of an approver
    api_error       a permanent model failure stopped the run

There is no check here for a loop that makes no progress and still finishes.
That absence is a finding rather than an oversight, and the harness supplies
the missing check in front of this worker rather than pretending Build 01 has
one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BUILD))

from agent import run_agent
from stub_client import StubClient


def read_trace(run_dir: Path, run_id: str) -> list[dict]:
    path = run_dir / f"{run_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line]


def handle(job, workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    client = StubClient(job["script"])

    result = run_agent(
        job.get("task", "Find what has been published and record it."),
        job.get("max_steps", 6),
        client=client,
        token_budget=job.get("token_budget", 100_000),
        run_dir=str(workspace),
        backoff_s=0.0,
    )

    events = [event["event"] for event in read_trace(workspace, result["run_id"])]
    trace = read_trace(workspace, result["run_id"])

    fired = []
    if result["status"] == "INCOMPLETE" and result.get("reason") == "step_cap":
        fired.append("step_cap")
    if result["status"] == "INCOMPLETE" and result.get("reason") == "budget":
        fired.append("token_budget")
    if result["status"] == "FAILED" and result.get("code") == "api_error":
        fired.append("api_error")
    for event in trace:
        if event.get("code") == "tool_disabled":
            fired.append("tool_disabled")
        if event["event"] == "tool_result" and event.get("status") == "blocked":
            fired.append("write_gate")

    # The tool calls the run made, in order, so the harness can ask whether
    # the loop was making progress. Build 01 does not ask.
    calls = [f"{event['tool']}:{json.dumps(event.get('args'), sort_keys=True)}"
             for event in trace if event["event"] == "tool_request"]

    return {
        "status": result["status"],
        "checks_fired": sorted(set(fired)),
        "events": events,
        "answer": {
            "steps": result.get("steps"),
            "reason": result.get("reason"),
            "has_answer": result.get("answer") is not None,
            "tool_calls": calls,
        },
        "detail": f"{result['status']} after {result.get('steps')} steps",
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, line in enumerate(sys.stdin):
            if not line.strip():
                continue
            try:
                result = handle(json.loads(line), root / f"job{index}")
            except Exception as error:  # noqa: BLE001
                result = {"status": "FAILED", "checks_fired": [], "events": [],
                          "answer": None,
                          "detail": f"{type(error).__name__}: {error}"}
            sys.stdout.write(json.dumps(result, default=str) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
