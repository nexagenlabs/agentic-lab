"""Stage 5: the remaining limits. Budget, error policy, write gate.

The circuit breaker arrives with the error policy, because a tool that has
failed three times running is not a transient problem, and retrying it is how
a run spends its whole budget on one broken thing.

Stages 2 to 4 are repeated here in full, because this file stands alone.
"""

import os
import time

from anthropic import Anthropic, APIConnectionError, APIError

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MAX_STEPS = 20

# The ceiling a run may spend. Checked before a call, never after.
TOKEN_BUDGET = 100_000

# Three consecutive failures from one tool is not bad luck, it is a broken
# tool. Disable it rather than spend the rest of the run rediscovering that.
FAILURE_LIMIT = 3

# Status codes that mean the same request may work in a moment. Everything
# else, a 400 above all, means the request itself is wrong and always will be.
TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

WRITE_TOOLS = {"save_note"}

# Approval arrives out of band, from a human. It is never read from the
# arguments the model supplied: a model asked whether its own write was
# approved will say yes.
APPROVALS: set[str] = set()


class TransientError(RuntimeError):
    """A tool failure that the same call might survive if tried again."""


import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Trace:
    def __init__(self, run_dir="runs"):
        self.run_id = uuid.uuid4().hex[:12]
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(run_dir) / f"{self.run_id}.jsonl"

    def write(self, event: str, **fields):
        record = {"run_id": self.run_id,
                  "ts": datetime.now(timezone.utc).isoformat(),
                  "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


# Stands in for a real esearch call, which arrives in Build 03.
CORPUS = [
    {"pmid": "31562799", "title": "Olaparib maintenance in ovarian carcinoma", "year": 2019},
    {"pmid": "30345884", "title": "Niraparib in recurrent ovarian carcinoma", "year": 2018},
    {"pmid": "28578601", "title": "PARP inhibitor resistance mechanisms", "year": 2017},
    {"pmid": "32268121", "title": "Rucaparib in prostate carcinoma", "year": 2020},
]


def _pubmed_esearch(query: str, retmax: int) -> list[str]:
    """Return the matching PMIDs. Build 03 replaces the body, not the name."""
    terms = query.lower().split()
    hits = [r for r in CORPUS if any(t in r["title"].lower() for t in terms)]
    return [r["pmid"] for r in hits[:retmax]]


def search_pubmed(query: str, max_results: int = 20) -> dict:
    """Stubbed until Build 03 replaces the body."""
    pmids = _pubmed_esearch(query, retmax=max_results)
    return {"status": "ok", "count": len(pmids), "pmids": pmids}


def save_note(text: str, approved_by: str, path: str = "notes.jsonl") -> dict:
    """Append one note to the notebook.

    ``approved_by`` is required: an unattributed write is not a record.
    """
    record = {
        "text": text,
        "approved_by": approved_by,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"status": "ok", "written": path, "approved_by": approved_by}


TOOLS = [
    {
        "name": "search_pubmed",
        "description": (
            "Searches PubMed and returns matching PMIDs. Use this to find "
            "literature when you do not already have identifiers. "
            "Do NOT use this to retrieve the text of a known PMID; "
            "use fetch_abstract for that."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_note",
        "description": (
            "Append a note to the laboratory notebook. Use this when the user "
            "has asked for a finding to be recorded. Do NOT use this to keep "
            "working notes: the notebook is a record other people read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "approved_by": {"type": "string"},
            },
            "required": ["text", "approved_by"],
        },
    },
]


def check_search_pubmed(args: dict) -> str | None:
    """Return a reason to refuse the call, or None to allow it."""
    query = args.get("query")
    if not isinstance(query, str) or len(query.strip()) < 3:
        return "query must be a string of at least three characters"
    max_results = args.get("max_results", 20)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return "max_results must be an integer"
    if not 1 <= max_results <= 200:
        return "max_results must be between 1 and 200"
    return None


def check_save_note(args: dict) -> str | None:
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        return "text must be a non-empty string"
    approved_by = args.get("approved_by")
    if not isinstance(approved_by, str) or not approved_by.strip():
        return "approved_by is required"
    return None


REGISTRY = {"search_pubmed": search_pubmed, "save_note": save_note}
CHECKS = {"search_pubmed": check_search_pubmed, "save_note": check_save_note}


def approved(name: str, args: dict) -> bool:
    """Whether a human has approved this write.

    The arguments the model supplied cannot answer this question, which is why
    ``args`` is read for nothing here. Approval has to arrive from outside the
    run, and ``APPROVALS`` stands in for wherever it arrives from.
    """
    return name in APPROVALS


def is_transient(error: APIError) -> bool:
    """A dropped connection never reached a server, so it has no status code
    to read. Everything else is judged on the code it came back with."""
    if isinstance(error, APIConnectionError):
        return True
    return getattr(error, "status_code", None) in TRANSIENT_STATUS


def run_agent(task: str, max_steps: int = MAX_STEPS) -> dict:
    trace = Trace()
    messages = [{"role": "user", "content": task}]
    steps = 0
    tokens_used = 0
    # Nothing has been measured yet, so nothing is assumed. The first call is
    # the one that produces the estimate every later call is judged against.
    estimated_next = 0
    retries = 0
    failures: dict[str, int] = {}
    disabled: set[str] = set()
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps,
                token_budget=TOKEN_BUDGET)

    while steps < max_steps:
        # Budget ceiling, checked BEFORE the call rather than after.
        if tokens_used + estimated_next > TOKEN_BUDGET:
            trace.write("halt", reason="budget")
            return {"status": "INCOMPLETE", "reason": "budget",
                    "steps": steps}

        steps += 1
        tools = [t for t in TOOLS if t["name"] not in disabled]
        trace.write("model_call", step=steps, model=MODEL)
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=2048, tools=tools, messages=messages,
            )
        except APIError as error:
            status_code = getattr(error, "status_code", None)
            # The retry takes a step of its own, so a nested loop cannot hide
            # from the ceiling.
            if is_transient(error) and retries == 0:
                retries += 1
                trace.write("model_error", step=steps,
                            status_code=status_code, retrying=True)
                time.sleep(2)
                continue
            trace.write("model_error", step=steps,
                        status_code=status_code, retrying=False)
            trace.write("halt", reason="api_error", steps=steps)
            return {"status": "FAILED", "code": "api_error", "steps": steps,
                    "status_code": status_code, "answer": None,
                    "run_id": trace.run_id}

        retries = 0
        spent = response.usage.input_tokens + response.usage.output_tokens
        tokens_used += spent
        # The turn just measured is the best estimate of the next one.
        estimated_next = spent
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason, tokens_used=tokens_used)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content
                           if b.type == "text")
            trace.write("halt", reason="complete", steps=steps, max_steps=max_steps)
            return {"status": "COMPLETE", "steps": steps,
                    "answer": text, "run_id": trace.run_id}

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.write("tool_request", step=steps, tool=block.name, args=block.input)
            if block.name in disabled:
                output = {"status": "error", "code": "tool_disabled", "tool": block.name}
            else:
                output = dispatch(block.name, block.input)
                # dispatch keeps the two argument signature the chapter prints,
                # so it has no trace to write to. The refusal is recorded here
                # instead, from the structured result it returned.
                if output["status"] == "blocked":
                    trace.write("tool_blocked", tool=block.name,
                                code=output["code"])
                elif output["status"] == "error":
                    trace.write("tool_rejected", tool=block.name,
                                code=output["code"], args=block.input)
                if output["status"] == "error":
                    failures[block.name] = failures.get(block.name, 0) + 1
                    if failures[block.name] >= FAILURE_LIMIT:
                        disabled.add(block.name)
                        trace.write("circuit_open", tool=block.name,
                                    failures=failures[block.name])
                else:
                    failures[block.name] = 0
            trace.write("tool_result", step=steps, tool=block.name,
                        status=output["status"], code=output.get("code"))
            results.append({"type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output)})
        messages.append({"role": "user", "content": results})

    trace.write("halt", reason="step_cap", steps=steps, max_steps=max_steps)
    return {"status": "INCOMPLETE", "steps": steps, "answer": None,
            "run_id": trace.run_id}


# The error policy and the write gate both live in dispatch, because both are
# decisions about whether a call happens at all. It sits below the loop that
# calls it, in the order the chapter introduces the two.
def dispatch(name, args):
    fn = REGISTRY.get(name)
    if fn is None:
        return {"status": "error", "code": "unknown_tool", "tool": name}

    if name in WRITE_TOOLS and not approved(name, args):
        return {"status": "blocked", "code": "awaiting_human_approval"}

    reason = CHECKS[name](args)
    if reason is not None:
        return {"status": "error", "code": "invalid_arguments", "detail": reason}

    for attempt in (1, 2):
        try:
            return fn(**args)
        except TransientError:
            if attempt == 2:
                return {"status": "error", "code": "tool_unavailable"}
            time.sleep(2 ** attempt)


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
