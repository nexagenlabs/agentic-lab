"""A stubbed stand-in for the Anthropic client, driven by a JSON script.

No test in this repository may reach the network, so every scenario the loop
has to survive is written down as data in ``fixtures/`` and replayed here.
The surface is exactly the part of ``anthropic.Anthropic`` that ``agent.py``
touches: ``client.messages.create(...)`` returning an object with ``model``,
``stop_reason``, ``content`` and ``usage``. Swapping the real client for this
one requires no change to ``agent.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anthropic import APIError

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Tokens charged for a turn whose fixture does not say. Any number will do;
# it only has to be stable so the budget assertions are deterministic.
DEFAULT_USAGE = {"input_tokens": 400, "output_tokens": 60}


class StubAPIError(APIError):
    """An API failure carrying a ``status_code``.

    A real ``anthropic.APIStatusError`` is an ``APIError`` with that attribute,
    and the attribute is the only thing the agent's error policy reads. There
    is no request to attach, because no request was ever made.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message, request=None, body=None)
        self.status_code = status_code


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class StubResponse:
    model: str
    stop_reason: str
    content: list[Any]
    usage: Usage


@dataclass
class StubMessages:
    """The ``client.messages`` namespace."""

    script: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> StubResponse:
        """Replay the next scripted turn, or raise the next scripted error."""
        turn = self._turn_for(len(self.calls))
        self.calls.append(kwargs)

        if turn["kind"] == "error":
            raise StubAPIError(turn["status_code"], turn.get("message", "stub error"))

        usage = Usage(**turn.get("usage", DEFAULT_USAGE))
        model = self.script.get("model", "stub-model-0000-00-00")

        if turn["kind"] == "tool_use":
            block = ToolUseBlock(
                id=f"toolu_{len(self.calls):03d}",
                name=turn["name"],
                input=turn["input"],
            )
            return StubResponse(model, "tool_use", [block], usage)

        block = TextBlock(text=turn["text"])
        return StubResponse(model, turn.get("stop_reason", "end_turn"), [block], usage)

    def _turn_for(self, index: int) -> dict[str, Any]:
        turns = self.script["turns"]
        if index < len(turns):
            return turns[index]
        if self.script.get("repeat_last"):
            return turns[-1]
        raise StubScriptExhausted(f"script ran out after {index} calls")


class StubScriptExhausted(RuntimeError):
    """The agent asked for one more turn than the fixture scripts."""


class StubClient:
    """Stands in for ``anthropic.Anthropic()``."""

    def __init__(self, script: dict[str, Any]) -> None:
        self.messages = StubMessages(script)

    @classmethod
    def from_fixture(cls, name: str) -> StubClient:
        return cls(load_script(name))


def load_script(name: str) -> dict[str, Any]:
    """Load ``fixtures/<name>.json``."""
    path = FIXTURES / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
