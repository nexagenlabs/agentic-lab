"""Stage 3: the loop. This is the whole idea of an agent, and it is short.

Stage 2 is repeated here in full, because this file stands alone. The new
code is ``check_search_pubmed``, ``dispatch`` and ``run_agent``.

``run_agent`` sits at the foot of the file, below the tools it dispatches to,
because a name used inside a function body need only exist by the time the
function is called.
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
    """Real implementation lives in the repo. Stub shown here."""
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
    """Return a reason to refuse the call, or None to allow it.

    Written out by hand so the reader can see what a schema would do for them.
    Build 02 replaces this with Pydantic and the behaviour does not change,
    which is why the bounds here are the bounds the Pydantic model declares.
    """
    query = args.get("query")
    if not isinstance(query, str) or len(query.strip()) < 3:
        return "query must be a string of at least three characters"
    max_results = args.get("max_results", 20)
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return "max_results must be an integer"
    if not 1 <= max_results <= 200:
        return "max_results must be between 1 and 200"
    return None


def dispatch(name: str, args: dict) -> dict:
    """Validate at the boundary, then call. The function body never sees a
    bad argument, and the caller never sees an exception."""
    if name != "search_pubmed":
        return {"status": "error", "code": "unknown_tool", "tool": name}
    reason = check_search_pubmed(args)
    if reason is not None:
        return {"status": "error", "code": "invalid_arguments", "detail": reason}
    return search_pubmed(**args)


import json

MAX_STEPS = 20

def run_agent(task: str, max_steps: int = MAX_STEPS) -> dict:
    messages = [{"role": "user", "content": task}]
    steps = 0

    while steps < max_steps:
        steps += 1
        response = client.messages.create(
            model=MODEL, max_tokens=2048, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content
                           if b.type == "text")
            return {"status": "COMPLETE", "steps": steps,
                    "answer": text}

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output = dispatch(block.name, block.input)
            results.append({"type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output)})
        messages.append({"role": "user", "content": results})

    return {"status": "INCOMPLETE", "steps": steps, "answer": None}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
