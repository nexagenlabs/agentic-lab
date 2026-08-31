# Build 07: Protocol Adapter

Introduced in **Chapter 6** of *The Agentic Lab*, second half.

Adapt a published protocol to a different cell line, and emit a diff naming
every parameter that changed, every parameter carried over unchanged, and
every parameter the source never stated.

## What the chapter prints

One file here appears verbatim in Chapter 6, and `tests/test_listings.py`
holds it to it.

| File | Printed as |
| --- | --- |
| `models.py` | Build 07: The Protocol Adapter |

`Adaptation` is the shape the rest of the build is arranged around: four lists
that every parameter must land in exactly one of, checked by a validator on
the model rather than by an instruction in a prompt.

## The adapted protocol is not the product. The diff is.

Chapter 6's failure account is an adapter that changed the concentrations it
was asked about and silently kept the seeding density and the endpoint it was
not. The wells went confluent, the dynamic range compressed, the IC50 came out
about twofold wrong, and every check the adapter ran passed. Nothing in that
is a model behaving badly. The output simply had nowhere to record what the
adapter had not thought about.

So the build is four lists, and the two that matter are the ones nobody asks
for. `carried_over_unchanged` is dangerous because a parameter kept on purpose
and a parameter kept by inattention look identical once the protocol is
printed. `not_stated_in_source` is worse, because it is the set of things
nobody can check.

## Silence about a Table 6.2 parameter is an error, not a default

All six of seeding density, incubation to endpoint, solvent tolerance, passage
number range, serum concentration and readout chemistry must appear in exactly
one of the four lists. That is a `model_validator` on `Adaptation`, not a line
in a prompt. A prompt instruction is a request; a validator is a refusal, and
this one cannot be talked out of it by a model having a bad day. A parameter in
no list raises, a parameter in two raises, and a misspelling raises as both,
because a misspelling is silence wearing a disguise.

## The model reads. Python decides.

`extract.py` asks one question: for each parameter, does this protocol state
it, and which sentence says so. It never sees the target cell line, so it
cannot adapt anything towards it even if it wanted to.

Everything that comes back then goes through `verify`, which is two mechanical
tests:

- the quoted evidence must appear in the protocol text, and
- every number in the reported value must appear in that quote.

The second is the one that earns its keep. Shown "cells were seeded at an
appropriate density in 96-well plates" and asked for a seeding density, a
model will sometimes answer 5000, because 5000 is what everybody uses, and it
will quote the sentence honestly while doing it. Checking that the quote
contains *a* digit is not enough: that sentence contains 96. Checking that the
quote contains 5000 is enough. The recorded extraction in `stub_client.py`
does exactly this, on purpose, so the gate proves the check works rather than
proving the stub behaves.

## Doubling time drives seeding density

The one piece of real arithmetic, and it is in Python:

```
doublings_lost = endpoint_h / source_doubling - endpoint_h / target_doubling
adapted_density = source_density * 2 ** doublings_lost
```

In 72 h a line doubling every 22 h completes 3.27 doublings and one doubling
every 55 h completes 1.31, so the slower line arrives at the readout 1.96
doublings behind. Seeding it 3.90 times denser puts both plates at the same
confluence when the assay is read, which is what the source protocol was
actually holding constant.

Where the source doubling time is unknown, the endpoint unstated, or the
scaling outside 0.2 to 5.0, seeding density goes to `requires_human_decision`.
It is never carried over silently, and `test_carryover_is_explicit` is that
sentence as a test.

The endpoint is held rather than scaled, and that is a decision rather than an
oversight: the readout chemistry and the plate constrain the endpoint far more
tightly than the cell line does, so the adaptation moves the density instead.
It is recorded in `carried_over_unchanged` so the decision is visible.

## The report is organised by a reporting standard

`adaptation_report.md` maps the diff onto the Good In Vitro Reporting
Standards categories: cell source and identity, quality control, materials,
culture conditions, design, analysis, data availability. No category is ever
omitted. A heading with nothing under it is the most informative line in the
document, and a report that quietly drops its empty sections reads as complete
when it is not.

## Run it

```python
from adapt import run_adaptation
from config import AGENT_MODEL
from report import write_report
from stub_client import StubClient          # or anthropic.Anthropic()

run = run_adaptation(
    "fixtures/source_protocols/ambiguous_density.md",
    "NSC-8810",
    StubClient(),
    AGENT_MODEL,
)
print(run.adaptation.as_dict()["not_stated_in_source"])
write_report(run, "adaptation_report.md")
```

The model name comes from `AGENT_MODEL` in the environment, with a default in
`config.py` and nowhere else.

## Tests

```
pytest builds/07-protocol-adapter/tests/
```

Twenty-six, none of which touches the network. The five the spec names are
present under those names; `test_every_table_parameter_is_classified` is
parametrised over all twelve source and target pairings in
`fixtures/expected/`, which were written out by hand from the protocol text
rather than generated from the adapter.

## The fixtures are fabricated

Every protocol, DOI, cell line, RRID and doubling time in `fixtures/` was
invented for this repository. `fixtures/README.md` says so at length, and it is
worth reading before you borrow a number from it: a doubling time is the input
this build multiplies a seeding density by, and a fabricated one produces a
confidently wrong plate.

## What is not here

No protocol execution, no plate layout, which is Build 06, and no attempt to
decide whether the adapted protocol is a good experiment. The build produces a
diff and stops.
