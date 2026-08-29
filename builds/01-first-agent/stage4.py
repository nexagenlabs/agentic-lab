"""Stage 4: the trace. One JSON object per line, written as the run happens.

JSONL from the first version, because a run you cannot replay is a run you
cannot debug, and because appending a line is the only write that survives a
process being killed halfway through.

Stages 2 and 3 are repeated here in full, because this file stands alone. The
new code is the ``Trace`` class and the trace calls inside the loop.
"""

import os

from anthropic import Anthropic

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


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
    }
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


def dispatch(name: str, args: dict, trace: "Trace") -> dict:
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


MAX_STEPS = 20


def run_agent(task: str, max_steps: int = MAX_STEPS) -> dict:
    trace = Trace()
    messages = [{"role": "user", "content": task}]
    steps = 0
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps)

    while steps < max_steps:
        steps += 1
        trace.write("model_call", step=steps, model=MODEL)
        response = client.messages.create(
            model=MODEL, max_tokens=2048, tools=TOOLS, messages=messages,
        )
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason)
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
            output = dispatch(block.name, block.input, trace)
            trace.write("tool_result", step=steps, tool=block.name,
                        status=output["status"], code=output.get("code"))
            results.append({"type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output)})
        messages.append({"role": "user", "content": results})

    trace.write("halt", reason="step_cap", steps=steps, max_steps=max_steps)
    return {"status": "INCOMPLETE", "steps": steps, "answer": None,
            "run_id": trace.run_id}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
