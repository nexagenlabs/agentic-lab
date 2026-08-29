"""The screening driver: one record per model call, driven by your list.

The loop is not free to wander. It walks the identifiers you handed it, and
every one of them leaves either a verdict or a logged gap. That is what the
assertion at the foot of the function is for, and why the count is taken in
Python rather than asked of the model.
"""

from agent import run_agent
from eutils import fetch_abstract
from models import Verdict
from prompts import build_task


def screen_corpus(pmid_list, criteria, trace):
    verdicts, failed = [], []

    for pmid in pmid_list:                # your list, not the model's
        record = fetch_abstract(pmid)
        result = run_agent(build_task(record, criteria), max_steps=4)

        if result["status"] != "COMPLETE":
            trace.write("record_failed", pmid=pmid,
                        reason=result["status"])
            failed.append(pmid)           # a gap, not a guess
            continue

        verdicts.append(Verdict(**result["answer"]))

    # Arithmetic in Python. Every record is a verdict or a logged gap.
    assert len(verdicts) + len(failed) == len(pmid_list)
    return verdicts, failed
