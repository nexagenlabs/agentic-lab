"""The dispatch boundary, with Pydantic doing the checking.

Build 01 checked arguments by hand so the reader could see what the checking
consists of. Here a schema does it, and the gain is not brevity: it is that
the rejection is typed, countable, and reported back to the model in terms
naming the field that was wrong, so the next turn can often correct itself.

``SearchPubMed`` and ``dispatch`` below are printed in Chapter 3. The second
tool, the registry and the declaration helper follow them, because the printed
listing has to read as the chapter prints it.
"""

from pydantic import BaseModel, Field, ValidationError


class SearchPubMed(BaseModel):
    query: str = Field(min_length=3)
    max_results: int = Field(default=20, ge=1, le=200)

SCHEMAS = {"search_pubmed": SearchPubMed}

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


# The second tool is declared after ``dispatch`` rather than beside the first,
# because the chapter prints ``SCHEMAS`` holding one entry and the printed page
# and this file may not disagree. A name a function body reads is resolved when
# the function runs, so the later entry is in place by the time anything calls.
class FetchAbstract(BaseModel):
    pmid: str = Field(pattern=r"^\d{1,8}$")


SCHEMAS["fetch_abstract"] = FetchAbstract


# Stands in for a real efetch call, which arrives in Build 03.
CORPUS = {
    "31562799": {
        "title": "Olaparib maintenance in ovarian carcinoma",
        "abstract": "Maintenance olaparib extended progression free survival.",
    },
    "30345884": {
        "title": "Niraparib in recurrent ovarian carcinoma",
        "abstract": "Niraparib showed benefit regardless of BRCA status.",
    },
    "28578601": {
        "title": "PARP inhibitor resistance mechanisms",
        "abstract": "Restoration of homologous recombination drives resistance.",
    },
}


def search_pubmed(query: str, max_results: int = 20) -> dict:
    """Return the PMIDs matching ``query``.

    ``count`` is computed here rather than asked of the model, because a model
    asked to count will sometimes be wrong and will never say so.
    """
    terms = query.lower().split()
    pmids = [
        pmid
        for pmid, record in CORPUS.items()
        if any(term in record["title"].lower() for term in terms)
    ]
    pmids = pmids[:max_results]
    return {"status": "ok", "count": len(pmids), "pmids": pmids}


def fetch_abstract(pmid: str) -> dict:
    """Return the abstract text for one PMID.

    A PMID that is well formed but unknown is not a validation failure: the
    schema cannot know what the corpus holds, so the miss is reported here as
    a structured error rather than raised.
    """
    record = CORPUS.get(pmid)
    if record is None:
        return {"status": "error", "code": "not_found", "pmid": pmid}
    return {
        "status": "ok",
        "pmid": pmid,
        "title": record["title"],
        "abstract": record["abstract"],
        "source": "pubmed-stub",
    }


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


def tool_declaration(name: str, description: str, schema: type[BaseModel]) -> dict:
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
