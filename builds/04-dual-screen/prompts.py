"""Two prompts, derived from one criteria file.

Independence has to be visible somewhere, and this is one of the two places
it lives. The criteria are identical, quoted verbatim from the same file into
both, because two screens judging against different rules are not two screens.
What differs is the order of work and the framing of the question.

Screen A works criterion by criterion and asks whether each holds. Screen B
starts from the exclusions and asks what would have to be true for the record
to survive. Those two routes reach the same answer on a clear record and
diverge on an unclear one, which is the divergence the agreement statistics
are there to measure. Two identically worded prompts would agree because they
are the same instrument read twice, and that number would mean nothing.

Neither prompt mentions the other screen. Neither is given the other's
verdicts. If it were, the second screen would not be a second screen.
"""

from typing import Any

from criteria import Criteria

# The asymmetry, stated to the model rather than assumed. A screen that does
# not know which of its two errors is the expensive one will minimise the
# wrong quantity. Identical in both prompts: it is a property of the task, not
# a stylistic choice, so it must not differ between screens.
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


def _answer_format(record: dict[str, Any], criteria: Criteria) -> str:
    ids = ", ".join(criteria.criterion_ids())
    return f"""ANSWER FORMAT

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


def build_task_a(record: dict[str, Any], criteria: Criteria) -> str:
    """Screen A: work forwards, criterion by criterion."""
    return f"""You are screening one record against written criteria. Judge only \
the record below. Do not use anything you know about the paper from elsewhere.

{_render_criteria(criteria)}

RECORD
{_render_record(record)}

HOW TO DECIDE

Take the inclusion criteria in order. For each one, decide from the text above
whether it holds, does not hold, or cannot be evaluated. Then check the
exclusions the same way.

If a criterion cannot be evaluated from the text provided, the answer is
"flag". Do not infer that a criterion fails because the abstract does not
mention it: a criterion you cannot judge is not a criterion that failed.

{ASYMMETRY}

Set confidence to "low" whenever you flag. Use "high" only when the text
settles every criterion you relied on.

{_answer_format(record, criteria)}"""


def build_task_b(record: dict[str, Any], criteria: Criteria) -> str:
    """Screen B: work backwards, from the exclusions inward."""
    return f"""Below is one record and the written criteria a screening protocol \
applies to it. Decide the record on the text given and on nothing else.

{_render_criteria(criteria)}

RECORD
{_render_record(record)}

HOW TO DECIDE

Begin with the exclusions. Ask whether the record trips any of them outright.
If it does, it is excluded and you need go no further, naming the exclusion
that caught it.

If it survives the exclusions, ask what would have to be true of this record
for it to be included, and then ask whether the text actually says so. A
record that would qualify if a missing detail went your way has not qualified:
you are being asked what the abstract establishes, not what it permits.

Where the text leaves a criterion genuinely undecidable, return "flag" rather
than choosing the more likely reading. Absence of a statement is not evidence
against it.

{ASYMMETRY}

Set confidence to "low" whenever you flag. Use "high" only when the text
settles every criterion you relied on.

{_answer_format(record, criteria)}"""


# Keyed so a configuration can name a prompt without importing the function.
PROMPTS = {"a": build_task_a, "b": build_task_b}
