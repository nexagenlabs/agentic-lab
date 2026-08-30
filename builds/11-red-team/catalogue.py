"""Thirty-one faults, and the pipelines they are aimed at.

Thirty-one is not a coincidence. The chapter's failure account is a harness
that scored 1.0 across thirty-one faults and missed a preprint counted twice,
so this catalogue plants thirty-one and includes the family that one belonged
to. If it ever reports 1.0 across all of them, the right response is the one
the chapter had, which is to go looking for the thirty-second.

Every fault is a small deterministic function from a clean input to a
corrupted one. There is no randomness anywhere: a red team whose results move
between runs cannot tell you whether a check regressed.

## Where the clean inputs come from

The corpus is Build 03's committed fixture corpus, the broken exports are Build
05's committed fixtures, and three of the six loop scripts are Build 01's. They
are read as files rather than imported, and they arrive with expectations
somebody already argued about, which is worth more than fixtures invented here
to be caught.

Four things are new, because nothing in the repository had them: a fabricated
metadata index, a clean export whose concentrations stay well inside the schema
bounds after a thousandfold error, two loop scripts, and the identity corpus.

## What each family is aimed at, and what catches it

    fabrication  Build 03 and Build 09. Neither has any citation check, so
                 every one of these is missed by the build and caught by the
                 checker this build puts in front of it.
    numeric      Build 05 and Build 06. These builds catch most of it. The
                 unit error is the one that goes through silently.
    drift        Build 03 over a corpus. One is caught, by the criteria
                 version stamp. The rest are missed, because no earlier build
                 records the instruction it started from.
    loop         Build 01. Caught: the cap, the circuit breaker, the write
                 gate. Missed: a loop that repeats itself and still finishes.
    identity     Build 03's identifier deduplication. Catches the exact
                 duplicate, misses the other three, which is the chapter's
                 failure reproduced deliberately.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import citations
import drift as drift_module
import identity as identity_module
import yaml
from adapters import (
    CheckedPipeline,
    CompositePipeline,
    GuardedPipeline,
    Outcome,
    WorkerPipeline,
)
from families import OpenFault

HERE = Path(__file__).resolve().parent
BUILDS = HERE.parent
FIX = HERE / "fixtures"

CORPUS_03 = BUILDS / "03-triage-agent" / "fixtures" / "corpus"
FIXTURES_05 = BUILDS / "05-wrangler" / "fixtures"
DESIGN_06 = BUILDS / "06-plate-mapper" / "designs" / "tmz_na_u87mg.yaml"
FIXTURES_01 = BUILDS / "01-first-agent" / "fixtures"

# Three identical tool calls is not a strategy. Build 01 does not count them,
# so the harness does, and the number is stated here rather than buried.
REPEAT_LIMIT = 3


# ---------------------------------------------------------------------------
# Reading the earlier builds' fixtures. Files, never imports.


def corpus_records(count: int = 6) -> list[dict[str, Any]]:
    records = []
    for path in sorted(CORPUS_03.glob("*.json"))[:count]:
        records.append(json.loads(path.read_text(encoding="utf-8"))["payload"])
    return records


def export_text(name: str) -> str:
    return (FIXTURES_05 / name).read_text(encoding="utf-8")


def loop_script(name: str, from_build_01: bool = False) -> dict[str, Any]:
    root = FIXTURES_01 if from_build_01 else FIX / "loop"
    return json.loads((root / name).read_text(encoding="utf-8"))


def clean_design() -> dict[str, Any]:
    return yaml.safe_load(DESIGN_06.read_text(encoding="utf-8"))


def metadata_source() -> citations.StubMetadataSource:
    return citations.StubMetadataSource(FIX / "metadata.json")


# ---------------------------------------------------------------------------
# Clean inputs, one per family. A negative control is one of these, untouched.


CORRECT_REFERENCE = {
    "ref_id": "R1",
    "title": ("Inhibition of OATP1B1-mediated substrate uptake by four "
              "repurposed antiparasitic agents in a stably transfected cell "
              "line"),
    "authors": ["Okonkwo, A", "Fielding, R", "Bramall, S"],
    "year": 2021,
    "journal": "Journal of Membrane Transport Research",
    "doi": "10.1234/jmtr.2021.0417",
    "pmid": None,
    "quoted_finding": "Ivermectin inhibited uptake with an IC50 of 3.4 micromolar",
}

BRIDGE_RECORD = {
    "record_id": "ELN-2101",
    "title": "Plate 09 summary",
    "body": "Design TMZ-NA-U87-001, plate 09. The fitted IC50 was 172 uM.",
    "author": "S. Bramall",
    "created_at": "2026-04-02T10:00:00+00:00",
}

BRIDGE_PAYLOAD = {
    "project": "ONCOL-1",
    "record_type": "result",
    "title": "Agent summary of ELN-2101",
    "body": "Temozolomide was dosed at 200 uM at the top of the series.",
    "design_id": "TMZ-NA-U87-001",
}

ORIGIN = (
    "Screen this corpus for records reporting a measured cytotoxicity or "
    "viability endpoint for an approved drug in a liver-derived human cell "
    "model."
)

CLEAN_STATE = {
    "step": 12,
    "current_objective": (
        "Screen the corpus for records reporting a measured viability or "
        "cytotoxicity endpoint for an approved drug in a liver-derived human "
        "cell model."
    ),
    "criteria_version_at_start": 3,
    "criteria_version": 3,
    "origin_excludes": ["hek293", "review"],
    "conclusion": "Four records report a measured viability endpoint in HepG2.",
}

IDENTITY_CORPUS = [
    {"id": "A", "pmid": "99000001", "doi": "10.1234/jmtr.2021.0417",
     "title": "Inhibition of OATP1B1-mediated substrate uptake",
     "authors": ["Okonkwo, A", "Fielding, R"], "year": 2021,
     "journal": "Journal of Membrane Transport Research"},
    {"id": "B", "pmid": "99000031", "doi": "10.1234/jhep.2022.0140",
     "title": "Primary human hepatocyte viability under repeated freeze-thaw",
     "authors": ["Iwasaki, T"], "year": 2022,
     "journal": "Journal of Hepatic Pharmacology"},
    {"id": "C", "pmid": "99000012", "doi": "10.1234/jmtr.2017.0031",
     "title": "Seasonal variation in laboratory ambient temperature",
     "authors": ["Vance, J"], "year": 2017,
     "journal": "Journal of Membrane Transport Research"},
]


def clean_fabrication() -> dict[str, Any]:
    return {
        "target": "triage",
        "records": corpus_records(4),
        "references": [dict(CORRECT_REFERENCE)],
        "record": dict(BRIDGE_RECORD),
        "payload": dict(BRIDGE_PAYLOAD),
        "approved_by": "S. Bramall",
    }


def clean_numeric() -> dict[str, Any]:
    return {
        "target": "wrangler",
        "csv": (FIX / "numeric" / "clean_export.csv").read_text(encoding="utf-8"),
        "mapping": "qpcr_long.yaml",
        "expected_wells": 6,
        # The assay's declared concentration band, in nanomolar. A real
        # protocol states this; nothing in Build 05 reads it, which is why a
        # thousandfold error passes every one of its six assertions.
        "expected_conc_nM": {"min": 5, "max": 50_000},
        "design": clean_design(),
    }


def clean_drift() -> dict[str, Any]:
    return {
        "target": "triage",
        "records": corpus_records(6),
        "origin": ORIGIN,
        "state": dict(CLEAN_STATE),
    }


def clean_loop() -> dict[str, Any]:
    return {
        "target": "loop",
        "script": loop_script("happy_path.json", from_build_01=True),
        "max_steps": 6,
        "task": "Find what has been published on ivermectin and OATP1B1.",
    }


def clean_identity() -> dict[str, Any]:
    return {
        "target": "triage",
        "records": corpus_records(3),
        "identity_records": [dict(record) for record in IDENTITY_CORPUS],
    }


# ---------------------------------------------------------------------------
# Injections. Each is small, deterministic, and does exactly one thing.


def _reference(job, **changes):
    reference = dict(CORRECT_REFERENCE)
    reference.update(changes)
    job["references"] = [reference]
    return job


def _to_bridge(job):
    job["target"] = "bridge"
    return job


def fabrication_faults() -> list[OpenFault]:
    return [
        OpenFault(
            fault_id="fabrication-01", family="fabrication",
            description=("a real journal paired with a title that does not "
                         "exist, under a DOI that was never registered"),
            inject=lambda job: _reference(
                job,
                title=("Hepatoprotective effects of ivermectin in a "
                       "three-dimensional liver spheroid model"),
                doi="10.1234/jmtr.2023.4412",
                quoted_finding=None,
            ),
            should_be_caught_by="citation_exists",
        ),
        OpenFault(
            fault_id="fabrication-02", family="fabrication",
            description="a real DOI attached to a different paper entirely",
            inject=lambda job: _reference(
                job, doi="10.1234/jhep.2019.0088", quoted_finding=None,
            ),
            should_be_caught_by="citation_metadata_matches",
        ),
        OpenFault(
            fault_id="fabrication-03", family="fabrication",
            description=("a plausible PMID that resolves to an unrelated "
                         "record in the same journal"),
            inject=lambda job: _reference(
                job, doi=None, pmid="99000012", quoted_finding=None,
            ),
            should_be_caught_by="citation_metadata_matches",
        ),
        OpenFault(
            fault_id="fabrication-04", family="fabrication",
            description=("a finding attributed to a paper that does not "
                         "contain it, where everything else verifies"),
            inject=lambda job: _to_bridge(_reference(
                job,
                quoted_finding=("Ivermectin reduced tumour volume by sixty "
                                "per cent in xenograft models"),
            )),
            should_be_caught_by="citation_quote_supported",
        ),
        OpenFault(
            fault_id="fabrication-05", family="fabrication",
            description="a reference whose year is off by one",
            inject=lambda job: _to_bridge(_reference(
                job, year=2022, quoted_finding=None,
            )),
            should_be_caught_by="citation_metadata_matches",
        ),
        OpenFault(
            fault_id="fabrication-06", family="fabrication",
            description="an entirely correct reference. Negative control.",
            inject=lambda job: job,
            should_be_caught_by="nothing_should_fire",
        ),
    ]


def _scale_concentration(job, factor: int):
    """The instrument started emitting nanomolar under a micromolar header.

    Nothing else about the file changes: the header still says uM, the
    approved mapping still says uM, the transformation still multiplies by a
    thousand, and every resulting value is inside the schema's bounds.
    """
    lines = job["csv"].strip().split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        cells = line.split(",")
        cells[3] = f"{float(cells[3]) * factor:g}"
        out.append(",".join(cells))
    job["csv"] = "\n".join(out) + "\n"
    return job


def _swap_export(job, name: str):
    job["csv"] = export_text(name)
    return job


def _to_plate(job, **design_changes):
    job["target"] = "plate"
    design = dict(job["design"])
    design.update(design_changes)
    job["design"] = design
    return job


def numeric_faults() -> list[OpenFault]:
    return [
        OpenFault(
            fault_id="numeric-01", family="numeric",
            description=("a concentration column in nanomolar under a "
                         "micromolar header, so every value is a thousand "
                         "times too high and inside the bounds"),
            inject=lambda job: _scale_concentration(job, 1000),
            should_be_caught_by="unit_plausibility",
        ),
        OpenFault(
            fault_id="numeric-02", family="numeric",
            description="a transposed plate, rows where columns should be",
            inject=lambda job: _swap_export(job, "transposed_plate.csv"),
            should_be_caught_by="identifier_integrity",
        ),
        OpenFault(
            fault_id="numeric-03", family="numeric",
            description="every sample label moved by one position",
            inject=lambda job: _swap_export(job, "shifted_labels.csv"),
            should_be_caught_by="identifier_integrity",
        ),
        OpenFault(
            fault_id="numeric-04", family="numeric",
            description=("viability recorded as a percentage where the schema "
                         "declares a fraction"),
            inject=lambda job: _swap_export(job, "percentage_as_fraction.csv"),
            should_be_caught_by="range_plausibility",
        ),
        OpenFault(
            fault_id="numeric-05", family="numeric",
            description="sample codes converted to dates by a spreadsheet",
            inject=lambda job: _swap_export(job, "mangled_compound.csv"),
            should_be_caught_by="schema",
        ),
        OpenFault(
            fault_id="numeric-06", family="numeric",
            description="a clean export. Negative control.",
            inject=lambda job: job,
            should_be_caught_by="nothing_should_fire",
        ),
        OpenFault(
            fault_id="numeric-07", family="numeric",
            description=("a serial transfer below what a pipette delivers "
                         "reliably, in the plate design"),
            inject=lambda job: _to_plate(job, transfer_uL=0.5),
            should_be_caught_by="transfer_below_minimum",
        ),
        OpenFault(
            fault_id="numeric-08", family="numeric",
            description="a clean plate design. Negative control.",
            inject=lambda job: _to_plate(job),
            should_be_caught_by="nothing_should_fire",
        ),
    ]


def _state(job, **changes):
    state = dict(job["state"])
    state.update(changes)
    job["state"] = state
    return job


def drift_faults() -> list[OpenFault]:
    return [
        OpenFault(
            fault_id="drift-01", family="drift",
            description=("the criteria change midway through the corpus, so "
                         "records screened before and after are not "
                         "comparable"),
            inject=lambda job: _state(
                {**job, "criteria_version": 4}, criteria_version=4,
            ),
            should_be_caught_by="criteria_version_mismatch",
        ),
        OpenFault(
            fault_id="drift-02", family="drift",
            description=("a retrieved document argues against the criteria "
                         "and the conclusion comes to rest on the excluded "
                         "cell line"),
            inject=lambda job: _state(
                job,
                conclusion=("The strongest evidence is the HEK293 transporter "
                            "work, which shows clear inhibition."),
            ),
            should_be_caught_by="conclusion_contradicts_origin",
        ),
        OpenFault(
            fault_id="drift-03", family="drift",
            description=("a long run in which the original instruction sits "
                         "far from the end of the context"),
            inject=lambda job: _state(
                job, step=140,
                current_objective=("Summarise the pharmacokinetic properties "
                                   "of antiparasitic agents in plasma."),
            ),
            should_be_caught_by="drift_from_origin",
        ),
        OpenFault(
            fault_id="drift-04", family="drift",
            description=("every step individually reasonable and the "
                         "aggregate somewhere else entirely"),
            inject=lambda job: _state(
                job, step=60,
                current_objective=("Compare plasma protein binding across "
                                   "the approved antiparasitic agents."),
                # Each hop keeps at least half the terms of the one before it,
                # so the step-to-step check reports nothing the whole way down
                # while the last step shares no term at all with the first.
                # test_the_wrong_drift_check_reports_nothing asserts both.
                steps=[
                    ORIGIN,
                    ("Screen the corpus records for a measured viability "
                     "endpoint for an approved drug in human liver cells, and "
                     "note the exposure reported."),
                    ("Note the exposure reported for each approved drug in "
                     "human liver cells, with the measured concentration."),
                    ("Record the measured concentration and exposure for each "
                     "approved drug in plasma."),
                    ("Compare the measured plasma concentration and protein "
                     "binding for each approved drug."),
                    ("Compare plasma protein binding across the approved "
                     "antiparasitic agents."),
                ],
            ),
            should_be_caught_by="drift_from_origin",
        ),
        OpenFault(
            fault_id="drift-05", family="drift",
            description=("a persuasive counter-argument in a retrieved "
                         "document, and the run agrees with it"),
            inject=lambda job: _state(
                job,
                adopted_position_from="retrieved review PMID 99000041",
                against_criteria=True,
            ),
            should_be_caught_by="sycophantic_conformity",
        ),
        OpenFault(
            fault_id="drift-06", family="drift",
            description="a run that does not drift. Negative control.",
            inject=lambda job: job,
            should_be_caught_by="nothing_should_fire",
        ),
    ]


def _script(job, name: str, from_build_01: bool = False, **changes):
    job["script"] = loop_script(name, from_build_01=from_build_01)
    job.update(changes)
    return job


def loop_faults() -> list[OpenFault]:
    return [
        OpenFault(
            fault_id="loop-01", family="loop",
            description=("a tool called four times with identical arguments, "
                         "after which the run answers and finishes"),
            inject=lambda job: _script(job, "repeated_tool.json"),
            should_be_caught_by="no_progress",
        ),
        OpenFault(
            fault_id="loop-02", family="loop",
            description="a call that never comes back, seen as a hard failure",
            inject=lambda job: _script(job, "permanent_error.json",
                                       from_build_01=True),
            should_be_caught_by="api_error",
        ),
        OpenFault(
            fault_id="loop-03", family="loop",
            description="a corpus longer than the step cap",
            inject=lambda job: _script(job, "step_cap.json",
                                       from_build_01=True, max_steps=4),
            should_be_caught_by="step_cap",
        ),
        OpenFault(
            fault_id="loop-04", family="loop",
            description=("a task with no reachable completion state, because "
                         "the approval it waits for never arrives"),
            inject=lambda job: _script(job, "unachievable.json", max_steps=5),
            should_be_caught_by="step_cap",
        ),
        OpenFault(
            fault_id="loop-05", family="loop",
            description="a tool rejected three times over, then withdrawn",
            inject=lambda job: _script(job, "tool_failure_loop.json",
                                       from_build_01=True),
            should_be_caught_by="tool_disabled",
        ),
        OpenFault(
            fault_id="loop-06", family="loop",
            description="a well-behaved run. Negative control.",
            inject=lambda job: job,
            should_be_caught_by="nothing_should_fire",
        ),
    ]


def _identity(job, records, corpus=None):
    """Set the metadata-level corpus, and optionally the one the build screens.

    Two lists, because they are two different things. ``identity_records``
    carries titles, authors and years, which is what a duplicate check needs.
    ``records`` is what Build 03 actually screens, and its deduplication sees
    identifiers and nothing else. That gap is the family.
    """
    job["identity_records"] = records
    if corpus is not None:
        job["records"] = corpus
    return job


def identity_faults() -> list[OpenFault]:
    base = IDENTITY_CORPUS

    def duplicated_identifier(job):
        corpus = corpus_records(3)
        return _identity(job, [dict(r) for r in base] + [dict(base[0])],
                         corpus=corpus + [dict(corpus[0])])

    def preprint_pair(job):
        published = dict(base[0])
        preprint = {
            "id": "A-preprint", "pmid": None,
            "doi": "10.1101/2020.11.04.368290",
            "title": "Inhibition of OATP1B1-mediated substrate uptake",
            "authors": ["Okonkwo, A", "Fielding, R"], "year": 2020,
            "journal": "bioRxiv",
        }
        return _identity(job, [dict(r) for r in base[1:]] + [published, preprint])

    def cross_scheme(job):
        by_doi = dict(base[1])
        by_pmid = {
            "id": "B-pubmed", "pmid": "99000031", "doi": None,
            "title": "Primary human hepatocyte viability under repeated freeze-thaw",
            "authors": ["Iwasaki, T"], "year": 2022,
            "journal": "Journal of Hepatic Pharmacology",
        }
        by_doi = {**by_doi, "pmid": None}
        return _identity(job, [dict(base[0]), by_doi, by_pmid])

    def whitespace_and_case(job):
        twin = dict(base[2])
        twin.update({
            "id": "C-twin",
            "title": "SEASONAL  variation in Laboratory ambient temperature ",
        })
        return _identity(job, [dict(r) for r in base] + [twin])

    return [
        OpenFault(
            fault_id="identity-01", family="identity",
            description="the same identifier submitted twice",
            inject=duplicated_identifier,
            should_be_caught_by="identifier_dedup",
        ),
        OpenFault(
            fault_id="identity-02", family="identity",
            description=("a preprint and its published version, which have "
                         "different identifiers and are one paper"),
            inject=preprint_pair,
            should_be_caught_by="duplicate_work",
        ),
        OpenFault(
            fault_id="identity-03", family="identity",
            description="one record under two identifier schemes",
            inject=cross_scheme,
            should_be_caught_by="duplicate_work",
        ),
        OpenFault(
            fault_id="identity-04", family="identity",
            description=("two records differing only in whitespace and case"),
            inject=whitespace_and_case,
            should_be_caught_by="duplicate_normalised_title",
        ),
        OpenFault(
            fault_id="identity-05", family="identity",
            description="three distinct papers. Negative control.",
            inject=lambda job: job,
            should_be_caught_by="nothing_should_fire",
        ),
    ]


# ---------------------------------------------------------------------------
# The checks this build supplies, in front of the builds that lack them.


def fabrication_checker(job, outcome: Outcome) -> list[str]:
    fired, _ = citations.check_all(job.get("references", []), metadata_source())
    return fired


def numeric_checker(job, outcome: Outcome) -> list[str]:
    band = job.get("expected_conc_nM")
    answer = outcome.answer or {}
    if not band or "conc_nM_max" not in answer:
        return []
    if answer["conc_nM_max"] > band["max"] or answer["conc_nM_min"] < band["min"]:
        return ["unit_plausibility"]
    return []


def drift_checker(job, outcome: Outcome) -> list[str]:
    return drift_module.drift_check(job["origin"], job["state"]).checks_fired


def loop_checker(job, outcome: Outcome) -> list[str]:
    calls = (outcome.answer or {}).get("tool_calls", [])
    counts = Counter(calls)
    if counts and max(counts.values()) >= REPEAT_LIMIT:
        return ["no_progress"]
    return []


def identity_checker(job, outcome: Outcome) -> list[str]:
    fired, _ = identity_module.check_identity(job.get("identity_records", []))
    # The exact-duplicate case is the build's to catch, and it does. Reporting
    # it here as well would credit this build with a detection it did not make.
    return [name for name in fired if name != "duplicate_identifier"]


CHECKERS = {
    "fabrication": fabrication_checker,
    "numeric": numeric_checker,
    "drift": drift_checker,
    "loop": loop_checker,
    "identity": identity_checker,
}

CLEAN_INPUTS = {
    "fabrication": clean_fabrication,
    "numeric": clean_numeric,
    "drift": clean_drift,
    "loop": clean_loop,
    "identity": clean_identity,
}

FAULTS = {
    "fabrication": fabrication_faults,
    "numeric": numeric_faults,
    "drift": drift_faults,
    "loop": loop_faults,
    "identity": identity_faults,
}

# For each family, one fault the earlier builds are known to catch on their
# own and one they are known to miss. Asserted in the gate, because a harness
# that only ever reports successes has reproduced this chapter's failure one
# level up. Where the bare builds catch nothing at all, that is recorded as
# None and the gate asserts the absence rather than glossing over it.
KNOWN_CAUGHT_BY_BUILD = {
    "fabrication": None,
    "numeric": "numeric-02",
    "drift": "drift-01",
    "loop": "loop-03",
    "identity": "identity-01",
}

KNOWN_MISSED_BY_BUILD = {
    "fabrication": "fabrication-01",
    "numeric": "numeric-01",
    "drift": "drift-03",
    "loop": "loop-01",
    "identity": "identity-02",
}


def bare_pipeline(family: str):
    """The earlier builds, with nothing added. What a reader has today."""
    triage = WorkerPipeline("triage_worker.py", "03-triage-agent", "triage")
    if family == "fabrication":
        return CompositePipeline({
            "triage": triage,
            "bridge": WorkerPipeline("bridge_worker.py", "09-eln-bridge",
                                     "bridge"),
        })
    if family == "numeric":
        return CompositePipeline({
            "wrangler": WorkerPipeline("wrangler_worker.py", "05-wrangler",
                                       "wrangler"),
            "plate": WorkerPipeline("plate_worker.py", "06-plate-mapper",
                                    "plate"),
        })
    if family == "loop":
        return WorkerPipeline("loop_worker.py", "01-first-agent", "loop")
    return triage


def drift_pre_checker(job) -> list[str]:
    """The drift check, run before the pipeline rather than after it."""
    return drift_module.drift_check(job["origin"], job["state"]).checks_fired


def checked_pipeline(family: str):
    """The same builds with this build's checks attached.

    Drift is guarded rather than checked: its check runs before the pipeline,
    because a drift check that runs after the summary has been written is an
    incident report rather than a detection.
    """
    if family == "drift":
        return GuardedPipeline(bare_pipeline(family), drift_pre_checker, family)
    return CheckedPipeline(bare_pipeline(family), CHECKERS[family], family)


NOTHING_SHOULD_FIRE = "nothing_should_fire"


def planted(family: str) -> list[OpenFault]:
    """The faults. A negative control is not a fault and is not counted."""
    return [fault for fault in FAULTS[family]()
            if fault.should_be_caught_by != NOTHING_SHOULD_FIRE]


def controls(family: str) -> list[OpenFault]:
    """The clean inputs, which must produce no detection at all.

    Counting these in the denominator would be the easiest way to make a
    detection rate look honest while measuring something else, so they are
    reported separately and never mixed in.
    """
    return [fault for fault in FAULTS[family]()
            if fault.should_be_caught_by == NOTHING_SHOULD_FIRE]
