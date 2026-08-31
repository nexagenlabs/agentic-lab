# Screening report

**Template for Chapter 4.** `builds/04-dual-screen/report.py` fills this in
from a run. This copy exists so you can see the shape without running anything,
and so you can adapt it for a screen built outside this repository.

If a field here cannot be filled, do not delete the row. An empty row is a
question somebody can ask; a deleted row is one nobody knows to ask.

Everything below is pasteable into a methods section with the placeholders
replaced. If you find yourself rewriting rather than filling in, tell me,
because the template is then wrong.

---

## Screening method

Records were screened against criteria file `{criteria_file}`, version
`{criteria_version}`, committed at `{criteria_commit}`.

Two independent screens were run over the same corpus of `{corpus_size}`
records, in the `{configuration}` configuration: `{screen_a_model}` and
`{screen_b_model}`, with separately worded prompts derived from the same
criteria file and results joined only at scoring.

A gold standard of `{gold_set_size}` records was screened by hand before the
agents ran. The set was enriched rather than sampled at random, comprising
every inclusion (`{n_inclusions}`), every flagged record (`{n_flags}`), every
designed case (`{n_designed}`) and `{n_seeded_negatives}` negatives drawn with
seed `{gold_seed}`. A random sample of that size from a corpus at
`{prevalence}` prevalence would be expected to contain no positives.

## Performance against the gold standard

| Metric | Screen A | Screen B |
|---|---|---|
| Sensitivity | `{sens_a}` | `{sens_b}` |
| Specificity | `{spec_a}` | `{spec_b}` |
| Negative predictive value | `{npv_a}` | `{npv_b}` |
| Positive predictive value | `{ppv_a}` | `{ppv_b}` |

Sensitivity is reported first because it is the only figure that says what was
lost. A false negative is a record removed from the review with no signal that
it happened; a false positive costs a reviewer about thirty seconds at full
text. Positive predictive value is reported last and is expected to be low: a
first-pass screen that hands you a pile which is mostly irrelevant but contains
everything relevant is working as intended.

Accuracy is not reported. At `{prevalence}` prevalence a screen that excluded
every record would score `{null_screen_accuracy}`.

## Agreement between the two screens

| | |
|---|---|
| Observed agreement | `{observed_agreement}` |
| Cohen's kappa | `{kappa}`, `{kappa_band}` |
| Prevalence-adjusted, bias-adjusted kappa | `{pabak}` |
| Gwet's AC1 | `{ac1}` |

Kappa is reported with its Landis and Koch band and alongside observed
agreement, because kappa falls as prevalence moves away from balance and
screening lives far from balance. `{agreement_commentary}`

## Adjudication

`{n_disagreements}` records were classified differently by the two screens and
were referred for human adjudication. None was resolved automatically. That
count is the real cost of the screen and is reported for that reason.

`{n_flagged}` records were flagged by at least one screen as unevaluable under
the criteria and were also referred.

## Provenance

| | |
|---|---|
| Run identifier | `{run_id}` |
| Date | `{run_date}` |
| Criteria version | `{criteria_version}` |
| Corpus snapshot | `{corpus_snapshot_id}` |
| Manifest | `{manifest_path}` |

## Limitations

`{limitations}`

*State at minimum: that the gold standard was constructed by the same person
who wrote the criteria, if it was; anything the criteria could not resolve; and
any respect in which the two screens were less independent than the
configuration implies.*
