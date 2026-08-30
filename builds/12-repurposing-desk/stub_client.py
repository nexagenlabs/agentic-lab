"""Offline stand-ins for the three tiers, and the replay client.

No test in this build reaches the network, and the desk never constructs a live
client anywhere. ``TieredClient`` is what a desk run uses. It answers
deterministically, counts tokens per tier, and every completion it returns is
written into the trace, which is what makes audit replay possible.

``ReplayClient`` serves the recorded completions back in order and checks that
the run asks for them in the same order it produced them. That last part is
what makes audit replay a check rather than a re-run: if the pipeline asked a
different question this time, the stage names would not line up and the replay
refuses rather than quietly producing the same outputs by another route.

``ForbiddenClient`` raises on any use at all. The gate patches the real client
to it and proves the patch bites before trusting an offline replay.

The screening rules are Build 03's, copied rather than imported. Copied because
each build stands alone; copied faithfully because a desk that screened by
looser rules than Build 03 would produce a shortlist nobody could compare with
Build 03's gold set. It is a stand-in for reading comprehension, not a
screening tool, so a disagreement with gold is a question about this file
first.
"""

from __future__ import annotations

import json
import re
from typing import Any

from config import MODEL_VERSION, RELATIVE_COST_PER_1K, TIERS

# Compounds this stub can recognise by name, enumerated rather than
# understood. It is a stand-in for reading comprehension: a drug the corpus
# names and this tuple does not is a drug the desk cannot see, and that is a
# limit of the stub rather than of the corpus. The list is the question's
# ``compound_ligands`` keys, and a test asserts the two agree, so a compound
# that can be docked can also be recognised.
KNOWN_COMPOUNDS = (
    "albendazole", "amiodarone", "chlorpromazine", "clozapine", "diclofenac",
    "fluconazole", "itraconazole", "ivermectin", "ketoconazole",
    "mebendazole", "metformin", "olanzapine", "paracetamol", "praziquantel",
    "rifampicin", "silibinin", "simvastatin", "troglitazone",
)

QUALIFYING = ("hepg2", "huh7", "heparg")
NON_QUALIFYING = ("hek293", "a549", "mcf-7", "caco-2", "hl-60", "sh-sy5y",
                  "huvec", "hacat", "hk-2", "aml12", "u87mg")
NON_HUMAN = ("rat", "murine", "mouse")
REVIEW_TYPES = {"review", "editorial", "comment", "congress"}

NO_DRUG = (
    "no drug", "no compound", "no treatment", "no pharmacological",
    "no small-molecule", "no individual constituent was isolated",
    "no fractionation was performed", "recombinant proteins rather than",
    "perturbation throughout is genetic", "exposure under study is physical",
    "variable under study is mechanical", "without any compound exposure",
    "no purified compound was administered",
)

# Sentences that mention a potency measure in order to deny it. Reading one of
# these as evidence of a numeric endpoint is the exact failure Build 03's
# corpus was built to catch.
DENIED_ENDPOINT = (
    "no viability percentage", "no percentage viability", "no potency value",
    "was not formally quantified", "no viability assay was performed",
    "no viability assay was run",
)

# The acronyms are scrubbed to a single space before a digit is looked for.
# Without that, "no IC50 or EC50 was determined" satisfies a naive search,
# because the digits of the second acronym sit within reach of the first.
ACRONYM = re.compile(r"\b(?:ic50|ec50)\b")
NEAR_ACRONYM = re.compile(r"\x20[^.]{0,40}?\d")
VIABILITY_THEN_NUMBER = re.compile(
    r"\bviability\b[^.]{0,30}?\d+(?:\.\d+)?\s*per cent"
)
NUMBER_THEN_VIABILITY = re.compile(
    r"\d+(?:\.\d+)?\s*per cent[^.]{0,30}?\bviability\b"
)
CRUDE_EXTRACT = re.compile(r"\b(?:crude|unfractionated)\b[^.]{0,40}\bextract")


class ModelWasCalled(AssertionError):
    """Something reached for a model during an offline replay."""


class ForbiddenClient:
    """Any use is a failure. There is no method to call safely."""

    def __init__(self, why: str = "audit replay must not call a model") -> None:
        self._why = why

    def __getattr__(self, name: str) -> Any:
        raise ModelWasCalled(f"{self._why}: something asked for .{name}")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelWasCalled(self._why)


def _tokens(prompt: str, reply: str) -> tuple[int, int]:
    """Deterministic and crude. Four characters to a token is close enough for
    a ratio, and a ratio is what the routing argument needs."""
    return max(1, len(prompt) // 4), max(1, len(reply) // 4)


class TieredClient:
    """Three tiers behind one call, with the routing recorded per stage.

    ``all_frontier`` is the comparison the chapter asks for. It changes which
    model answers and nothing else, so the completions are identical and the
    shortlist cannot move. That is the claim: the extra spend buys nothing.
    """

    def __init__(self, all_frontier: bool = False) -> None:
        self.all_frontier = all_frontier
        self.tokens: dict[str, dict[str, int]] = {
            tier: {"input": 0, "output": 0} for tier in TIERS
        }
        self.calls: list[dict[str, Any]] = []

    def tier_for(self, requested: str) -> str:
        return "frontier" if self.all_frontier else requested

    def model_for(self, requested: str) -> str:
        return TIERS[self.tier_for(requested)]

    def complete(self, stage: str, tier: str, prompt: str,
                 payload: dict[str, Any] | None = None,
                 item: str = "") -> str:
        """One completion. The text is a function of the payload, not the tier.

        Deliberately so. If the tier changed the answer, the all-frontier
        comparison would be measuring two things at once and the chapter's
        claim about routing could not be tested at all.
        """
        reply = _answer(stage, payload or {})
        used = self.tier_for(tier)
        prompt_tokens, reply_tokens = _tokens(prompt, reply)
        self.tokens[used]["input"] += prompt_tokens
        self.tokens[used]["output"] += reply_tokens
        self.calls.append({
            "stage": stage, "tier": used, "model": TIERS[used], "item": item,
            "input_tokens": prompt_tokens, "output_tokens": reply_tokens,
        })
        return reply

    def cost(self) -> float:
        """Relative units, not currency. Ratios are the transferable part."""
        total = 0.0
        for tier, counts in self.tokens.items():
            total += ((counts["input"] + counts["output"]) / 1000.0
                      * RELATIVE_COST_PER_1K[tier])
        return round(total, 4)

    def uses(self) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for call in self.calls:
            seen[call["tier"]] = {"id": call["model"],
                                  "version": MODEL_VERSION,
                                  "tier": call["tier"]}
        return [seen[tier] for tier in sorted(seen)]


class ReplayDiverged(RuntimeError):
    """The replay asked for something the recorded run did not ask for."""


class ReplayClient:
    """Serves recorded completions back, in order, checking the stage matches.

    This is not a model and does not pretend to be one. It is the trace,
    exposed through the same call signature so that ``run_desk`` can be
    re-executed without a single line of replay-specific branching inside it.
    """

    def __init__(self, recorded: list[dict[str, Any]]) -> None:
        self.recorded = list(recorded)
        self.position = 0
        self.tokens: dict[str, dict[str, int]] = {
            tier: {"input": 0, "output": 0} for tier in TIERS
        }
        self.calls: list[dict[str, Any]] = []

    def tier_for(self, requested: str) -> str:
        return requested

    def model_for(self, requested: str) -> str:
        return TIERS[requested]

    def complete(self, stage: str, tier: str, prompt: str,
                 payload: dict[str, Any] | None = None,
                 item: str = "") -> str:
        if self.position >= len(self.recorded):
            raise ReplayDiverged(
                f"the replay asked for a completion at stage {stage!r} and "
                f"the trace has only {len(self.recorded)}. The pipeline is "
                "asking more of the model than it did when the trace was "
                "written."
            )
        entry = self.recorded[self.position]
        if entry["stage"] != stage:
            raise ReplayDiverged(
                f"completion {self.position} was recorded at stage "
                f"{entry['stage']!r} and the replay asked for it at "
                f"{stage!r}. The run is not following the same path, so "
                "matching outputs would not mean what they appear to."
            )
        self.position += 1
        self.calls.append({"stage": stage, "tier": tier, "item": item})
        return entry["text"]

    def cost(self) -> float:
        return 0.0

    def uses(self) -> list[dict[str, str]]:
        return []


# ---------------------------------------------------------------------------
# The answers. Deterministic functions of the payload, never of the tier.


def compounds_in(text: str) -> list[str]:
    lowered = text.lower()
    return sorted({name for name in KNOWN_COMPOUNDS if name in lowered})


def has_numeric_endpoint(text: str) -> bool:
    """A number attached to IC50, EC50 or a viability percentage."""
    if any(phrase in text for phrase in DENIED_ENDPOINT):
        return False
    scrubbed = ACRONYM.sub(" ", text)
    if NEAR_ACRONYM.search(scrubbed):
        return True
    if VIABILITY_THEN_NUMBER.search(text):
        return True
    return bool(NUMBER_THEN_VIABILITY.search(text))


def liver_model(text: str) -> bool | None:
    """True, False, or None where the record names no model at all.

    None is the interesting value, and it is what produces the flags the
    triage loop exists to resolve. A record that names no model has not failed
    the criterion, it has left it unevaluable, and the criteria say to flag
    rather than infer a failure from silence.
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


def fires_no_drug(text: str) -> bool:
    if any(phrase in text for phrase in NO_DRUG):
        return True
    return bool(CRUDE_EXTRACT.search(text))


def _screen(payload: dict[str, Any]) -> dict[str, Any]:
    """One record against the criteria. Build 03's rules, copied."""
    text = f"{payload.get('title', '')} {payload.get('abstract', '')}".lower()
    types = {kind.lower() for kind in payload.get("publication_types") or []}
    compounds = compounds_in(text)

    if types & REVIEW_TYPES:
        return {"decision": "exclude", "compounds": compounds,
                "reason": "publication type is a review, editorial, comment "
                          "or conference abstract"}
    if fires_no_drug(text):
        return {"decision": "exclude", "compounds": compounds,
                "reason": "no qualifying small-molecule drug treatment"}

    numeric = has_numeric_endpoint(text)
    liver = liver_model(text)

    if liver is None or (not numeric and len(text.split()) < 40):
        return {"decision": "flag", "compounds": compounds,
                "reason": "the cell model is not named, so liver_model cannot "
                          "be evaluated from this abstract"}
    if not numeric:
        return {"decision": "exclude", "compounds": compounds,
                "reason": "no numerical endpoint is reported"}
    if not liver:
        return {"decision": "exclude", "compounds": compounds,
                "reason": "the model named is not a qualifying human liver "
                          "model"}
    return {"decision": "include", "compounds": compounds,
            "reason": "a numerical endpoint in a qualifying human liver model"}


def _triage(payload: dict[str, Any]) -> dict[str, Any]:
    """The full-text step, which has more to read than the abstract did.

    Step one asks what to fetch, step two reads the methods, step three
    answers. That is what makes this an agent loop rather than a chain: it
    takes an action, reads the result, and decides again.
    """
    step = int(payload.get("step", 1))
    if step == 1:
        return {"action": "fetch_full_text", "pmid": payload.get("pmid")}
    if step == 2:
        return {"action": "read_methods", "pmid": payload.get("pmid")}

    text = str(payload.get("full_text", "")).lower()
    compounds = compounds_in(text) or list(payload.get("compounds", []))
    if any(name in text for name in QUALIFYING) and has_numeric_endpoint(text):
        return {"action": "answer", "decision": "include",
                "reason": "the methods name a qualifying human liver model "
                          "that the abstract did not",
                "compounds": compounds}
    return {"action": "answer", "decision": "exclude",
            "reason": "the full text settles the criterion the abstract left "
                      "open, and it is not satisfied",
            "compounds": compounds}


def _protocol(payload: dict[str, Any]) -> dict[str, Any]:
    step = int(payload.get("step", 1))
    if step == 1:
        return {"action": "read_design", "design_id": payload.get("design_id")}
    return {
        "action": "answer",
        "cell_line": payload.get("target_line"),
        "compounds": payload.get("compounds", []),
        "top_conc_uM": 400,
        "dilution_factor": 2,
        "n_steps": 5,
        "readout": "MTT at 570 nm with a 630 nm reference",
        "adapted_from": payload.get("design_id"),
        "caveat": ("Concentrations are carried over from the source design. "
                   "They have not been checked against a dose response in "
                   "this line, and a person must do that before anything is "
                   "pipetted."),
    }


def _mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """A column mapping proposal, in Build 05's shape.

    Proposed once per instrument and replayed thereafter, which is why this
    stage is an agent loop that almost never runs one.
    """
    return {
        "instrument": payload.get("instrument"),
        "layout": "long",
        "header_row": 0,
        "columns": [
            {"source_column": "Conc (uM)", "target_column": "conc",
             "detected_unit": "uM", "confidence": "high",
             "unit_evidence": "Read from the file: the unit is in the header "
                              "cell itself, Conc (uM), on line 1."},
        ],
        "approved_by": None,
    }


ANSWERS = {"abstract_screening": _screen, "full_text_triage": _triage,
           "protocol_adaptation": _protocol, "export_mapping": _mapping}


def _answer(stage: str, payload: dict[str, Any]) -> str:
    handler = ANSWERS.get(stage)
    if handler is None:
        raise ValueError(f"this stub has no answer for stage {stage!r}")
    return json.dumps(handler(payload), sort_keys=True)


def parse(text: str) -> dict[str, Any]:
    """Read a completion, or say so. Never guess at a malformed reply."""
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        body = json.loads(match.group(0))
    if not isinstance(body, dict):
        raise TypeError("a completion must be one JSON object")
    return body
