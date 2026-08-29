"""Offline stand-ins for the Anthropic client. No test may reach the network.

Two of them, because the tests ask two different questions.

``ScriptedClient`` replays a fixture, turn by turn, and is the right tool for
asking what the loop does when a call fails or a reply is malformed.

``ScreeningClient`` actually screens. It reads the record named in the prompt
and applies the criteria as literally as a few dozen lines of Python can, then
returns a verdict. It exists so that screening the corpus is a real comparison
against ``gold.json`` rather than a rehearsal of answers written into a
fixture. A scripted stub asked whether the corpus is labelled correctly can
only tell you what you already typed.

It is a stub standing in for reading comprehension, not a screening tool. The
cell-model vocabulary below is enumerated rather than understood, so treat a
disagreement with gold as a question about this file first.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cache
from anthropic import APIError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEFAULT_USAGE = {"input_tokens": 700, "output_tokens": 120}


class StubAPIError(APIError):
    """An API failure carrying a status_code, which is all the policy reads."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message, request=None, body=None)
        self.status_code = status_code


class StubScriptExhausted(RuntimeError):
    """The agent asked for one more turn than the fixture scripts."""


@dataclass
class TextBlock:
    text: str
    type: str = "text"


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


# ---------------------------------------------------------------------------
# The screening stub


# Models this stub can recognise by name. Anything here that is not one of the
# four the criteria admit is a named model that fails liver_model, which is a
# different thing from a record that names no model at all.
QUALIFYING = ("hepg2", "huh7", "heparg")
NON_QUALIFYING = (
    "hek293", "a549", "mcf-7", "caco-2", "hl-60", "sh-sy5y", "huvec", "hacat",
    "hk-2", "aml12", "keratinocyte", "cardiomyocyte", "fibroblast",
    "endothelial cell", "proximal tubule",
)
NON_HUMAN = ("rat", "murine", "mouse")

# Phrases by which a record says, in terms, that nothing qualifying was given.
NO_DRUG = (
    "no drug", "no compound", "no treatment", "no pharmacological",
    "no small-molecule", "no individual constituent was isolated",
    "no fractionation was performed", "recombinant proteins rather than",
    "perturbation throughout is genetic", "exposure under study is physical",
    "variable under study is mechanical", "without any compound exposure",
    "no purified compound was administered",
)

REVIEW_TYPES = {"review", "editorial", "comment", "congress"}


# Sentences that mention a potency measure in order to deny it. Reading one of
# these as evidence of a numeric endpoint is the exact failure this corpus was
# built to catch, and the first version of this stub committed it.
DENIED_ENDPOINT = (
    "no viability percentage", "no percentage viability", "no potency value",
    "was not formally quantified", "no viability assay was performed",
    "no viability assay was run",
)


def _has_numeric_endpoint(text: str) -> bool:
    """A number attached to IC50, EC50 or a viability percentage.

    The acronyms are scrubbed to a placeholder before the digit is looked for.
    Without that, "no IC50 or EC50 was determined" satisfies a naive search,
    because the digits of the second acronym sit within reach of the first.
    """
    if any(phrase in text for phrase in DENIED_ENDPOINT):
        return False
    scrubbed = re.sub(r"\b(?:ic50|ec50)\b", "\x00", text)
    if re.search(r"\x00[^.]{0,40}?\d", scrubbed):
        return True
    if re.search(r"\bviability\b[^.]{0,30}?\d+(?:\.\d+)?\s*per cent", text):
        return True
    return bool(re.search(r"\d+(?:\.\d+)?\s*per cent[^.]{0,30}?\bviability\b", text))


def _liver_model(text: str) -> bool | None:
    """True, False, or None where the record names no model at all.

    None is the interesting value. A record that names no model has not failed
    this criterion, it has left it unevaluable, and the criteria say to flag
    rather than to infer a failure from silence.
    """
    if "hek293" in text:
        return False
    if "primary human hepatocyte" in text:
        return True
    if any(word in text for word in NON_HUMAN) and "hepatocyte" in text:
        return False
    if any(line in text for line in QUALIFYING):
        return True
    if any(line in text for line in NON_QUALIFYING):
        return False
    if "hepatocyte" in text:
        return True
    return None


def _fires_no_drug(text: str) -> bool:
    """Whether the record describes no qualifying drug treatment.

    The crude-extract test is a proximity match within one sentence, not a
    search for the word anywhere. 99000061 opens by describing what crude
    preparations are like before reporting a standardised one, and a looser
    test excludes it on the strength of a word in a sentence about something
    else.
    """
    if any(phrase in text for phrase in NO_DRUG):
        return True
    return bool(re.search(r"\b(?:crude|unfractionated)\b[^.]{0,40}\bextract", text))


def screen_record(record: dict[str, Any], criteria_version: int) -> dict[str, Any]:
    """Apply the criteria to one record and return a verdict payload."""
    text = f"{record.get('title', '')} {record.get('abstract', '')}".lower()
    pmid = record["pmid"]
    types = {t.lower() for t in record.get("publication_types") or []}

    def verdict(decision, met, failed, reason, confidence):
        return {
            "pmid": pmid, "decision": decision, "criteria_met": met,
            "criteria_failed": failed, "reason": reason[:300],
            "confidence": confidence, "criteria_version": criteria_version,
        }

    if types & REVIEW_TYPES:
        return verdict("exclude", [], ["review"],
                       "Publication type is a review, editorial, comment or "
                       "conference abstract.", "high")

    if _fires_no_drug(text):
        return verdict("exclude", [], ["no_drug"],
                       "No qualifying small-molecule drug treatment: the "
                       "record describes no defined chemical entity given at "
                       "a stated concentration.", "high")

    numeric = _has_numeric_endpoint(text)
    liver = _liver_model(text)

    # A criterion that cannot be judged is not a criterion that failed.
    if liver is None or (not numeric and len(text.split()) < 40):
        return verdict("flag", [], [],
                       "The text does not settle every criterion: the cell "
                       "model is not named, so liver_model cannot be "
                       "evaluated from this abstract.", "low")

    met = [name for name, held in (("numeric_endpoint", numeric),
                                   ("liver_model", liver)) if held]
    failed = [name for name, held in (("numeric_endpoint", numeric),
                                      ("liver_model", liver)) if not held]
    if failed:
        return verdict("exclude", met, failed,
                       f"Fails {failed[0]}: the record does not satisfy that "
                       "inclusion criterion.", "high")
    return verdict("include", met, [],
                   "Reports a numerical endpoint in a qualifying human liver "
                   "model with a defined drug treatment.", "high")


class ScreeningMessages:
    def __init__(self, corpus_dir, criteria_version, fail_on, unparsable_on):
        self.corpus_dir = Path(corpus_dir)
        self.criteria_version = criteria_version
        self.fail_on = set(fail_on)
        self.unparsable_on = set(unparsable_on)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> StubResponse:
        self.calls.append(kwargs)
        task = kwargs["messages"][0]["content"]
        match = re.search(r"PMID:\s*(\d+)", task)
        if match is None:
            raise StubScriptExhausted("no PMID in the task")
        pmid = match.group(1)

        if pmid in self.fail_on:
            raise StubAPIError(400, f"stubbed permanent failure for {pmid}")

        usage = Usage(**DEFAULT_USAGE)
        if pmid in self.unparsable_on:
            block = TextBlock(text="I am afraid I cannot answer that.")
            return StubResponse("stub-screener-1", "end_turn", [block], usage)

        record = cache.read(pmid, self.corpus_dir)
        payload = screen_record(record, self.criteria_version)
        block = TextBlock(text=json.dumps(payload))
        return StubResponse("stub-screener-1", "end_turn", [block], usage)


class ScreeningClient:
    """A client that screens the record named in the prompt."""

    def __init__(self, corpus_dir=None, criteria_version=3, fail_on=(),
                 unparsable_on=()) -> None:
        self.messages = ScreeningMessages(
            corpus_dir or FIXTURES / "corpus", criteria_version,
            fail_on, unparsable_on,
        )


# ---------------------------------------------------------------------------
# The scripted stub, for questions about the loop rather than the criteria


@dataclass
class ScriptedMessages:
    script: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> StubResponse:
        turn = self._turn_for(len(self.calls))
        self.calls.append(kwargs)
        if turn["kind"] == "error":
            raise StubAPIError(turn["status_code"], turn.get("message", "stub error"))
        usage = Usage(**turn.get("usage", DEFAULT_USAGE))
        block = TextBlock(text=turn["text"])
        model = self.script.get("model", "stub-model-0000-00-00")
        return StubResponse(model, turn.get("stop_reason", "end_turn"), [block], usage)

    def _turn_for(self, index: int) -> dict[str, Any]:
        turns = self.script["turns"]
        if index < len(turns):
            return turns[index]
        if self.script.get("repeat_last"):
            return turns[-1]
        raise StubScriptExhausted(f"script ran out after {index} calls")


class ScriptedClient:
    """Replays a fixture script, turn by turn."""

    def __init__(self, script: dict[str, Any]) -> None:
        self.messages = ScriptedMessages(script)

    @classmethod
    def from_fixture(cls, name: str) -> ScriptedClient:
        path = FIXTURES / f"{name}.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))
