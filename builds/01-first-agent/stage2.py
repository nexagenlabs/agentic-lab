"""Stage 2: one tool, and the declaration that tells the model about it.

Still not an agent. The model can now ask for the tool, but nothing here
answers the request.
"""

from typing import Any

from anthropic import Anthropic
from config import MODEL

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


if __name__ == "__main__":
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[SEARCH_PUBMED],
        messages=[{"role": "user", "content": "What is published on olaparib?"}],
    )
    print(response.stop_reason)
    print(response.content)
