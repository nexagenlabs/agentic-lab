"""The task handed to the model for one record.

Everything the model is asked to do is here, in one string, so that a reader
who wants to know why a verdict came out the way it did has one place to look.
Two things in it are load-bearing rather than decorative: the instruction to
flag rather than guess, and the sentence explaining the asymmetry that makes
flagging the cheaper error.
"""

from typing import Any

from criteria import Criteria

# The asymmetry, stated to the model rather than assumed. A screen that does
# not know which of its two errors is the expensive one will minimise the
# wrong quantity.
ASYMMETRY = (
    "A flagged record costs a human thirty seconds. A wrong verdict costs a "
    "paper. When those two are in tension, flag."
)


def _render_criteria(criteria: Criteria) -> str:
    lines = [f"QUESTION: {criteria.question.strip()}", ""]
    lines.append("INCLUDE only if ALL of these hold:")
    for rule in criteria.include_if_all:
        lines.append(f"  [{rule.id}] {rule.text.strip()}")
    if criteria.exclude_if_any:
        lines.append("")
        lines.append("EXCLUDE if ANY of these hold:")
        for rule in criteria.exclude_if_any:
            lines.append(f"  [{rule.id}] {rule.text.strip()}")
    return "\n".join(lines)


def _render_record(record: dict[str, Any]) -> str:
    types = ", ".join(record.get("publication_types") or []) or "not stated"
    return "\n".join(
        [
            f"PMID: {record['pmid']}",
            f"TITLE: {record.get('title', '')}",
            f"JOURNAL: {record.get('journal', 'not stated')}",
            f"YEAR: {record.get('year', 'not stated')}",
            f"PUBLICATION TYPES: {types}",
            "ABSTRACT:",
            record.get("abstract", ""),
        ]
    )


def build_task(record: dict[str, Any], criteria: Criteria) -> str:
    """Build the screening task for one record.

    The criteria are quoted into the prompt rather than summarised, so that
    the text the model judged against is the text on disk, and the version
    stamped on the verdict is the version that was actually applied.
    """
    ids = ", ".join(criteria.criterion_ids())
    return f"""You are screening one record against written criteria. Judge only \
the record below. Do not use anything you know about the paper from elsewhere.

{_render_criteria(criteria)}

RECORD
{_render_record(record)}

HOW TO DECIDE

Work criterion by criterion. For each one, decide from the text above whether
it holds, does not hold, or cannot be evaluated.

If a criterion cannot be evaluated from the text provided, the answer is
"flag". Do not infer that a criterion fails because the abstract does not
mention it: a criterion you cannot judge is not a criterion that failed.
A record you flag with confidence "low" goes to a human, which is the correct
destination for a record this text cannot settle.

{ASYMMETRY}

Set confidence to "low" whenever you flag. Use "high" only when the text
settles every criterion you relied on.

ANSWER FORMAT

Reply with one JSON object and nothing else. No prose before or after, no code
fence. The fields are:

  "pmid":             "{record['pmid']}"
  "decision":         "include", "exclude" or "flag"
  "criteria_met":     list of criterion ids that hold
  "criteria_failed":  list of criterion ids that caused an exclusion
  "reason":           one sentence, at most 300 characters, naming the
                      criterion that decided it
  "confidence":       "high" or "low"
  "criteria_version": {criteria.version}

Valid criterion ids are: {ids}. Cite an id in criteria_failed only when that
criterion is why the record is excluded."""
