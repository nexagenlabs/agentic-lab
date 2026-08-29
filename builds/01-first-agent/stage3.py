"""Stage 3: the loop. This is the whole idea of an agent, and it is short.

Stage 2 is repeated here in full, because this file stands alone. The new
code is ``check_search_pubmed``, ``dispatch`` and ``run_agent``.
"""

import json
import os
from typing import Any

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


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate at the boundary, then call. The function body never sees a
    bad argument, and the caller never sees an exception."""
    if name != "search_pubmed":
        return {"status": "error", "code": "unknown_tool", "tool": name}
    reason = check_search_pubmed(args)
    if reason is not None:
        return {"status": "error", "code": "invalid_arguments", "detail": reason}
    return search_pubmed(**args)


def run_agent(task: str, max_steps: int = 20) -> dict[str, Any]:
    client = Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    while steps < max_steps:
        steps += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[SEARCH_PUBMED],
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            return {"status": "COMPLETE", "steps": steps, "answer": answer}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = dispatch(block.name, block.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": results})
    return {"status": "INCOMPLETE", "steps": steps, "answer": None}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
