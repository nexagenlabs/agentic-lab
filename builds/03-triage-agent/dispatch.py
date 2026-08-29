"""The typed dispatch boundary, carried over from Build 02.

The schemas are the same idea as Build 02: a malformed call never reaches the
function body, the rejection is countable in the trace, and the model gets an
error naming the field that was wrong. What changed is underneath. These two
tools now reach NCBI rather than a stubbed corpus, so a bad argument is no
longer merely embarrassing: it is a request sent to somebody else's server.

Screening does not offer these tools. The agent judges a record it already
holds. They exist for the part of the work that goes looking for records.
"""

from typing import Any

import eutils
from pydantic import BaseModel, Field, ValidationError


class SearchPubMed(BaseModel):
    query: str = Field(min_length=3)
    max_results: int = Field(default=20, ge=1, le=200)


class FetchAbstract(BaseModel):
    pmid: str = Field(pattern=r"^\d{1,8}$")


SCHEMAS: dict[str, type[BaseModel]] = {
    "search_pubmed": SearchPubMed,
    "fetch_abstract": FetchAbstract,
}


def search_pubmed(query: str, max_results: int = 20) -> dict[str, Any]:
    """Return the PMIDs matching ``query``.

    ``count`` is computed here rather than asked of the model, because a model
    asked to count will sometimes be wrong and will never say so.
    """
    pmids = eutils._pubmed_esearch(query, retmax=max_results)
    return {"status": "ok", "count": len(pmids), "pmids": pmids}


def fetch_abstract(pmid: str) -> dict[str, Any]:
    """Return one record, from the cache where possible."""
    return eutils.fetch_abstract(pmid)


REGISTRY = {"search_pubmed": search_pubmed, "fetch_abstract": fetch_abstract}

DESCRIPTIONS = {
    "search_pubmed": (
        "Searches PubMed and returns matching PMIDs. Use this to find "
        "literature when you do not already have identifiers. "
        "Do NOT use this to retrieve the text of a known PMID; "
        "use fetch_abstract for that."
    ),
    "fetch_abstract": (
        "Fetches the title and abstract for one PMID you already hold. Use "
        "this when you have an identifier and need what the paper actually "
        "says. Do NOT use this to discover papers you cannot name; "
        "use search_pubmed for that."
    ),
}


def tool_declaration(name: str, description: str, schema: type[BaseModel]) -> dict[str, Any]:
    """Build the declaration the SDK expects, with the schema generated.

    Generated, never hand written: a declaration typed out a second time
    drifts from the model that enforces it, and then the model is told one
    thing while the code requires another.
    """
    return {
        "name": name,
        "description": description,
        "input_schema": schema.model_json_schema(),
    }


TOOLS = [
    tool_declaration(name, DESCRIPTIONS[name], schema)
    for name, schema in SCHEMAS.items()
]


def dispatch(name, args, trace):
    schema = SCHEMAS.get(name)
    if schema is None:
        return {"status": "error", "code": "unknown_tool", "tool": name}
    try:
        validated = schema(**args)
    except ValidationError as exc:
        trace.write("tool_rejected", tool=name, errors=exc.error_count())
        return {"status": "error", "code": "invalid_arguments",
                "detail": exc.errors()[0]["msg"]}
    return REGISTRY[name](**validated.model_dump())
