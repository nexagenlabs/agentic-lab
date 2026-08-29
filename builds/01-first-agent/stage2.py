"""Stage 2: one tool, and the declaration that tells the model about it.

Still not an agent. The model can now ask for the tool, but nothing here
answers the request. This file stands alone: type it and run it.
"""

import os

from anthropic import Anthropic

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")


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


if __name__ == "__main__":
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=TOOLS,
        messages=[{"role": "user", "content": "What is published on olaparib?"}],
    )
    print(response.stop_reason)
    print(response.content)
