"""The run being replayed, small enough to hold in your head.

The pipeline is a screening run in the shape of Build 03: a corpus, a versioned
criteria file, an enrichment call per batch of records, and one model verdict
per record. It exists so that the two replays have something real to reproduce,
and it is deliberately the smallest thing that still has all four sources of
divergence in it: code, model, inputs and the world.

The split below is the part worth copying into a real pipeline.

``screen`` is the live half. It calls out, it calls the model, and it writes
every completion to the trace verbatim.

``outputs_from_completions`` is the deterministic half. Given the model's own
words it produces the outputs, in Python, with no model and no network. Both
replays end here, which is why audit replay can reproduce a run byte for byte
with the vendor gone.

Every number in the outputs is counted here rather than asked for. A model that
is asked how many records it included will sometimes be wrong, and it will be
wrong in a way that reads perfectly.
"""

from __future__ import annotations

import json
from typing import Any

from hashing import canonical_json, hash_json

ENRICHMENT_ENDPOINT = "https://enrichment.example/v1/records"

VERDICTS_PATH = "outputs/verdicts.json"
SUMMARY_PATH = "outputs/summary.json"

# Six records per enrichment call. The batch size matters to the fixtures: it
# is why four revised responses can move six verdicts, which is the shape of
# the chapter's failure account.
BATCH_SIZE = 6


def batches(record_ids: list[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [record_ids[start: start + size]
            for start in range(0, len(record_ids), size)]


def enrichment_query(batch: list[str]) -> str:
    return "ids=" + ",".join(batch)


def outputs_from_completions(completion_texts: list[str],
                             criteria_version: int) -> dict[str, str]:
    """The outputs, from the model's own words. No model, no network.

    Sorted by record identifier so the order the corpus happened to be read in
    cannot change a digest, and counted in Python because arithmetic is not a
    thing to ask a model for.
    """
    verdicts = sorted((json.loads(text) for text in completion_texts),
                      key=lambda verdict: verdict["id"])
    for verdict in verdicts:
        verdict["criteria_version"] = criteria_version

    decisions = [verdict["decision"] for verdict in verdicts]
    summary = {
        "corpus_size": len(verdicts),
        "criteria_version": criteria_version,
        "included": decisions.count("include"),
        "excluded": decisions.count("exclude"),
        "flagged": decisions.count("flag"),
    }
    return {VERDICTS_PATH: canonical_json(verdicts),
            SUMMARY_PATH: canonical_json(summary)}


def screen(corpus: list[dict[str, Any]], criteria: dict[str, Any],
           client: Any, enrichment: Any, trace: Any) -> dict[str, str]:
    """The live run: fetch, ask, record, then hand over to the deterministic half.

    ``enrichment`` stands in for the database. It is a callable rather than a
    URL because the point of this build is what gets recorded about a call, not
    how the call is made, and every response it returns is hashed into the
    manifest and written into the trace.
    """
    by_id = {record["id"]: record for record in corpus}
    order = sorted(by_id)
    calls: list[dict[str, Any]] = []
    facts: dict[str, dict[str, Any]] = {}

    for batch in batches(order):
        query = enrichment_query(batch)
        response = enrichment(batch)
        digest = hash_json(response)
        trace.write("external_call", endpoint=ENRICHMENT_ENDPOINT, query=query,
                    response=response, response_sha256=digest)
        calls.append({"endpoint": ENRICHMENT_ENDPOINT, "query": query,
                      "response_sha256": digest})
        facts.update(response)

    texts = []
    for record_id in order:
        text = client.complete(by_id[record_id], criteria, facts[record_id])
        trace.write("model_completion", record_id=record_id,
                    model=client.model, version=client.version, text=text)
        texts.append(text)

    return {"outputs": outputs_from_completions(texts, criteria["version"]),
            "external_calls": calls, "completions": texts}
