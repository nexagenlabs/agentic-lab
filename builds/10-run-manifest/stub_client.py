"""Offline stand-ins. No test in this build reaches the network.

``StubModel`` screens a record deterministically and returns the raw JSON text
a model would have returned, which the trace then stores verbatim. It is what
the stored run was recorded with and what ``verify_replay`` calls.

``ForbiddenClient`` raises on any use at all. It is not a mock of anything; it
is an assertion with a call signature. ``audit_replay`` must work with the
vendor gone, and the honest way to test that is to make any attempt to reach a
model an error rather than to hope none happens. The gate passes it in, and it
also patches ``httpx`` so a call from anywhere else in the stack is equally
fatal. A test that passes because nothing happened to call out has established
nothing about what happens when something does.
"""

from __future__ import annotations

import json
from typing import Any


class ModelWasCalled(AssertionError):
    """Something reached for a model during an offline replay.

    An AssertionError rather than a RuntimeError on purpose: this is a test
    instrument, and a pipeline catching RuntimeError broadly should not be able
    to swallow it and carry on looking offline.
    """


class ForbiddenClient:
    """Any attribute access is a failure. There is no method to call safely."""

    def __init__(self, why: str = "audit replay must not call a model") -> None:
        self._why = why

    def __getattr__(self, name: str) -> Any:
        raise ModelWasCalled(f"{self._why}: something asked for .{name}")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelWasCalled(self._why)


class StubModel:
    """A screener with no opinions, so the outputs are a function of the inputs.

    The verdict depends on the record and on the enrichment fact fetched for
    it, which is what lets the drifted fixture change six verdicts by revising
    four responses and nothing else.
    """

    def __init__(self, model: str = "stub-screener",
                 version: str = "2026-05-01") -> None:
        self.model = model
        self.version = version
        self.calls = 0

    def complete(self, record: dict[str, Any], criteria: dict[str, Any],
                 facts: dict[str, Any]) -> str:
        self.calls += 1
        if facts.get("retracted"):
            decision, reason = "exclude", "the upstream record is retracted"
        elif facts.get("ambiguous"):
            decision, reason = "flag", "the endpoint could not be determined"
        elif not facts.get("has_numeric_endpoint"):
            decision, reason = "exclude", "no numerical endpoint is reported"
        elif record["year"] < criteria["earliest_year"]:
            decision, reason = "exclude", "published before the criteria window"
        else:
            decision, reason = "include", "reports a numerical endpoint in window"
        return json.dumps(
            {"id": record["id"], "decision": decision, "reason": reason,
             "confidence": "high" if decision != "flag" else "low"},
            sort_keys=True,
        )
