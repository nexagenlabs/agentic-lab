"""The report, written to be pasted into a methods section without editing.

That constraint drives everything here. It means the numbers arrive with their
denominators, the gold set arrives with the rule that built it and the seed
that drew it, kappa arrives with its Landis and Koch word, and the count sent
to human adjudication is stated rather than implied. A reader who has to open
the JSON to understand the table has been handed a worse document than a
sentence saying nothing.

It also means the report says what was not computed and why. A methods section
that omits accuracy without comment invites a reviewer to ask for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f} per cent"


def _num(value: float) -> str:
    return f"{value:.3f}"


def render_report(manifest: dict[str, Any]) -> str:
    """Render the manifest as a methods-section paragraph plus tables."""
    gold = manifest["gold_set"]
    perf = manifest["screen_a_performance"]
    agree = manifest["agreement"]
    adj = manifest["adjudication"]
    screens = manifest["screens"]

    overlap = gold["designed_also_counted_elsewhere"]
    overlap_note = (
        f" The categories overlap: {overlap} "
        f"{'record is' if overlap == 1 else 'records are'} counted in more than "
        "one row above, a designed case that is also an inclusion or a flag, so "
        "the rows sum to more than the total. The set is a union and each "
        "record appears in it once."
        if overlap
        else ""
    )

    return f"""# Screening report

Run `{manifest["run_id"]}`, criteria version {manifest["criteria_version"]}.

## Method

Records were screened independently by two screens over the same corpus of
{manifest["corpus_size"]} records, using criteria version
{manifest["criteria_version"]} as recorded in `{manifest["criteria_file"]}`.
The two screens shared no state: each wrote its verdicts to its own file, and
the files were joined only at scoring time. The screens used differently
worded prompts derived from the same criteria file, and different models
({screens["screen_a"]} and {screens["screen_b"]}), in the
`{screens["mode"]}` configuration.

Performance was measured against an enriched gold set of {gold["total"]}
records drawn from the {gold["corpus_size"]} record corpus. The set was not
sampled at random: a random sample of this size from a corpus at this
prevalence would contain too few positives to estimate sensitivity at all. It
comprises every inclusion, every flag and every designed case in the corpus,
together with {gold["seeded_negatives"]} negatives drawn with seed
{gold["seed"]} from the records those categories did not take.

## Gold set composition

| Category | Records |
| --- | --- |
| Inclusions | {gold["inclusions"]} |
| Flags | {gold["flags"]} |
| Designed cases | {gold["designed_cases"]} |
| Seeded negatives | {gold["seeded_negatives"]} |
| **Total (union)** | **{gold["total"]}** |

Seed: `{gold["seed"]}`. Corpus: {gold["corpus_size"]} records.{overlap_note}

## Performance against the gold set

Screen A, {screens["screen_a"]}, on {perf["gold_size"]} gold records.

| Statistic | Value |
| --- | --- |
| Sensitivity | {_pct(perf["sensitivity"])} ({perf["true_positives"]}/{perf["true_positives"] + perf["false_negatives"]}) |
| Specificity | {_pct(perf["specificity"])} ({perf["true_negatives"]}/{perf["true_negatives"] + perf["false_positives"]}) |
| Negative predictive value | {_pct(perf["negative_predictive_value"])} |
| Positive predictive value | {_pct(perf["positive_predictive_value"])} |

Records lost, meaning true inclusions this screen excluded outright:
{", ".join(f"`{p}`" for p in perf["records_lost"]) or "none"}.

A record the screen flagged is not counted as lost. A flag sends the record to
a person, which is where a record the abstract cannot settle is supposed to go.

## Agreement between the two screens

Over {agree["n"]} records screened by both.

| Statistic | Value |
| --- | --- |
| Observed agreement | {_pct(agree["observed_agreement"])} |
| Cohen's kappa | {_num(agree["kappa"])} ({agree["kappa_band"]}) |
| PABAK | {_num(agree["pabak"])} |
| Gwet's AC1 | {_num(agree["ac1"])} |

Observed agreement and kappa diverge here, and the divergence is the point.
The two screens agreed on {_pct(agree["observed_agreement"])} of records, which
sounds strong, while kappa is {_num(agree["kappa"])}, which Landis and Koch
would call {agree["kappa_band"]}. The gap is a prevalence artefact: most
records in a screening corpus are exclusions, so two screens agree constantly
by exclusion alone and kappa charges almost all of that agreement to chance.
PABAK and AC1 model chance differently and land higher. All three are reported
because reporting any one alone invites a reader to believe it.

## Human adjudication

{adj["sent_to_human_adjudication"]} of {adj["records_compared"]} records
({_pct(adj["share_of_corpus"])}) went to human adjudication, listed in
`{Path(manifest["adjudication_file"]).name}`, beside this report, with both
verdicts and both reasons side by side. None was resolved automatically.
That count is the real cost of this screen and should be read as such.

## What is not reported

Accuracy is not computed. At this prevalence a screen that excluded every
record without reading any of them would score above eighty-five per cent, so
the number rewards doing nothing and misleads anyone who has not checked the
prevalence first. Sensitivity is reported first instead, because it is the only
statistic that says what was lost.
"""


def write_report(path: str | Path, manifest: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(manifest), encoding="utf-8")
    return path
