"""Stage 4: the trace. One JSON object per line, written as the run happens.

JSONL from the first version, because a run you cannot replay is a run you
cannot debug, and because appending a line is the only write that survives a
process being killed halfway through.

Stages 2 and 3 are repeated here in full, because this file stands alone. The
new code is the ``Trace`` class and the trace calls inside the loop.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from anthropic import Anthropic

MODEL = os.environ.get("AGENT_MODEL", "claude-opus-5")


SEARCH_PUBMED = {
    "name": "search_pubmed",
    "description": (
        "Search PubMed for papers matching a query and return their PMIDs, "
        "titles and years. Use this when you need to find papers you do not "
        "already know about, for example to see what has been published on a "
        "target. Do NOT use this to retrieve the text of a known PMID: it "
        "returns metadata only, and a PMID you already hold needs no search."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free text query, at least three characters.",
            },
            "max_results": {
                "type": "integer",
                "description": "How many records to return, 1 to 50. Defaults to 5.",
            },
        },
        "required": ["query"],
    },
}


# Stands in for a real esearch call, which arrives in Build 03.
CORPUS = [
    {"pmid": "31562799", "title": "Olaparib maintenance in ovarian carcinoma", "year": 2019},
    {"pmid": "30345884", "title": "Niraparib in recurrent ovarian carcinoma", "year": 2018},
    {"pmid": "28578601", "title": "PARP inhibitor resistance mechanisms", "year": 2017},
    {"pmid": "32268121", "title": "Rucaparib in prostate carcinoma", "year": 2020},
]


class Trace:
    """Append-only JSONL for one run.

    One JSON object per line, written as the run happens, because a run you
    cannot replay is a run you cannot debug.
    """

    def __init__(self, run_dir: str = "runs") -> None:
        self.run_id = uuid4().hex[:12]
        self.path = Path(run_dir) / f"{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
        }
        record.update(fields)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


def _pubmed_esearch(query: str, max_results: int) -> list[dict[str, Any]]:
    """Stubbed PubMed search. Build 03 replaces the body, not the signature."""
    terms = query.lower().split()
    hits = [r for r in CORPUS if any(t in r["title"].lower() for t in terms)]
    return hits[:max_results]


def search_pubmed(query: str, max_results: int = 5) -> dict[str, Any]:
    """Return records matching ``query``.

    ``count`` is computed here rather than asked of the model, because a model
    asked to count will sometimes be wrong and will never say so.
    """
    hits = _pubmed_esearch(query, max_results)
    return {
        "status": "ok",
        "count": len(hits),
        "results": hits,
        "source": "pubmed-stub",
    }


def check_search_pubmed(args: dict[str, Any]) -> str | None:
    """Return a reason to refuse the call, or None to allow it.

    Written out by hand so the reader can see what a schema would do for them.
    Build 02 replaces this with Pydantic and the behaviour does not change.
    """
    query = args.get("query")
    if not isinstance(query, str) or len(query.strip()) < 3:
        return "query must be a string of at least three characters"
    max_results = args.get("max_results", 5)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return "max_results must be an integer"
    if not 1 <= max_results <= 50:
        return "max_results must be between 1 and 50"
    return None


def dispatch(name: str, args: dict[str, Any], trace: Trace) -> dict[str, Any]:
    """Validate at the boundary, then call. A rejection goes to the trace, so
    an argument the model keeps getting wrong is visible after the run."""
    if name != "search_pubmed":
        trace.write("tool_rejected", tool=name, code="unknown_tool")
        return {"status": "error", "code": "unknown_tool", "tool": name}
    reason = check_search_pubmed(args)
    if reason is not None:
        trace.write("tool_rejected", tool=name, code="invalid_arguments",
                    detail=reason, args=args)
        return {"status": "error", "code": "invalid_arguments", "detail": reason}
    return search_pubmed(**args)


def run_agent(task: str, max_steps: int = 20) -> dict[str, Any]:
    client = Anthropic()
    trace = Trace()
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps)
    while steps < max_steps:
        steps += 1
        trace.write("model_call", step=steps, model=MODEL)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[SEARCH_PUBMED],
            messages=messages,
        )
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason)
        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            trace.write("halt", reason="complete", steps=steps, max_steps=max_steps)
            return {"status": "COMPLETE", "steps": steps, "answer": answer,
                    "run_id": trace.run_id}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.write("tool_request", step=steps, tool=block.name, args=block.input)
            result = dispatch(block.name, block.input, trace)
            trace.write("tool_result", step=steps, tool=block.name,
                        status=result["status"], code=result.get("code"))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": results})
    trace.write("halt", reason="step_cap", steps=steps, max_steps=max_steps)
    return {"status": "INCOMPLETE", "reason": "step_cap", "steps": steps,
            "answer": None, "run_id": trace.run_id}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
