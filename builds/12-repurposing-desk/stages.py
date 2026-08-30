"""Table 12.1 as data, and the nine stages it describes.

The table is in this file as a list rather than in the README as prose,
because `test_only_three_stages_are_agent_loops` walks it. A table a test can
read is a table that cannot quietly stop being true.

## What the levels mean

    script                       no model anywhere in it
    chain                        a fixed sequence of steps, which may or may
                                 not include a model call. Screening is a
                                 chain with one call per record and no
                                 iteration: it cannot choose to do more work.
    agent loop                   takes an action, reads the result, decides
                                 again. This is the expensive one and the
                                 chapter's argument is that three is the right
                                 number of them.
    agent once, script
    thereafter                   an agent loop that runs once per instrument
                                 and a replayed mapping every time after.
    script with a gate           deterministic, and refuses rather than
                                 warning.

Three stages ever run a loop: full-text triage, instrument export mapping and
protocol adaptation. Everything else is a chain or a script. That is the
design that survived, rather than a compromise, and `desk.py` is deliberately
one function calling deterministic stages rather than a coordinator delegating
to specialist agents. One study measured multi-agent systems at four to two
hundred and twenty times the tokens of single-agent equivalents, and a rebuild
found eighty per cent of a five-agent system's tokens going on agents
describing their work to each other.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from config import MODEL_VERSION
from models import (
    Candidate,
    DockingResult,
    Pose,
    Ranked,
    Resolved,
    Screened,
    StructureRecord,
    Targets,
    Verdict,
)
from provenance import ModelUse, RunManifest, StageCost
from stub_client import parse

HERE = Path(__file__).resolve().parent
BUILDS = HERE.parent
REPO = BUILDS.parent

CORPUS_DIR = BUILDS / "03-triage-agent" / "fixtures" / "corpus"
CRITERIA_FILE = BUILDS / "03-triage-agent" / "criteria" / "repurposing_v3.yaml"
STRUCTURES_DIR = BUILDS / "08-dock-loop" / "fixtures" / "structures"
VINA_DIR = BUILDS / "08-dock-loop" / "fixtures" / "vina_output"
DESIGN_FILE = BUILDS / "06-plate-mapper" / "designs" / "tmz_na_u87mg.yaml"

VINA_SCORE = re.compile(r"REMARK VINA RESULT:\s*(-?\d+\.\d+)")

# Recorded in the manifest and passed to the engine explicitly, because search
# is stochastic and a run at exhaustiveness 8 is not a repeat of one at 16.
SEED = 20260829
EXHAUSTIVENESS = 16
ENGINE = "recorded-vina-1.2.5"

# How many steps the triage loop is allowed. A loop with no cap is the failure
# Build 01 exists to prevent, nine builds ago and still true.
TRIAGE_STEP_CAP = 4
PROTOCOL_STEP_CAP = 3


@dataclass(frozen=True)
class Stage:
    name: str
    description: str
    level: str

    @property
    def is_agent_loop(self) -> bool:
        """Does this stage ever run a model loop?

        ``agent once, script thereafter`` counts. It runs a loop the first
        time it sees an instrument, and a stage that runs a loop once is a
        stage that can run a loop.
        """
        return self.level in ("agent loop", "agent once, script thereafter")


TABLE_12_1: tuple[Stage, ...] = (
    Stage("corpus_retrieval", "Corpus retrieval and deduplication", "script"),
    Stage("abstract_screening", "Abstract screening against criteria",
          "chain, one model call per record"),
    Stage("full_text_triage", "Full-text triage of ambiguous records",
          "agent loop"),
    Stage("export_mapping", "Instrument export mapping",
          "agent once, script thereafter"),
    Stage("transformation", "Transformation, units, assertions", "script"),
    Stage("structure_acquisition", "Structure acquisition and preparation",
          "chain"),
    Stage("docking", "Docking execution and parsing", "script"),
    Stage("ranking", "Ranking and shortlist assembly", "script with a gate"),
    Stage("protocol_adaptation", "Protocol adaptation", "agent loop"),
)

AGENT_LOOPS = tuple(stage.name for stage in TABLE_12_1 if stage.is_agent_loop)


class DeskRefused(RuntimeError):
    """A stage refused, naming the check that refused it."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


class timed:
    """Measure a stage and record it. Measured, never estimated.

    The wall clock here is the wall clock of this run on this machine. With
    recorded fixtures standing in for a docking engine and a model API it is
    small, and the accounting says so rather than substituting the figure a
    real run would produce.
    """

    def __init__(self, manifest: RunManifest, stage: str, level: str,
                 human_minutes: int = 0, human_note: str = "") -> None:
        self.manifest = manifest
        self.stage = stage
        self.level = level
        self.human_minutes = human_minutes
        self.human_note = human_note

    def __enter__(self) -> Self:
        self.started = time.perf_counter()
        self.calls_before = len(getattr(self.manifest.client, "calls", []))
        self.manifest.trace.write("stage_started", stage=self.stage,
                                  level=self.level)
        return self

    def __exit__(self, *_: object) -> None:
        calls = getattr(self.manifest.client, "calls", [])[self.calls_before:]
        tokens: dict[str, int] = {}
        per_item: dict[str, int] = {}
        for call in calls:
            tier = call["tier"]
            tokens[tier] = tokens.get(tier, 0) + call.get(
                "input_tokens", 0) + call.get("output_tokens", 0)
            item = str(call.get("item", ""))
            per_item[item] = per_item.get(item, 0) + 1
        self.manifest.record_stage(StageCost(
            stage=self.stage, level=self.level,
            seconds=round(time.perf_counter() - self.started, 4),
            tokens=tokens, model_calls=len(calls),
            # The number that separates a chain from a loop, measured rather
            # than declared. A chain makes one call per item however many
            # items it has; a loop calls again about the same item, having
            # read what came back the first time. Screening makes sixty-one
            # calls and is a chain; triage makes nine and is a loop.
            max_calls_per_item=max(per_item.values(), default=0),
            human_minutes=self.human_minutes, human_note=self.human_note,
        ))
        self.manifest.trace.write("stage_finished", stage=self.stage,
                                  model_calls=len(calls))


def ask(manifest: RunManifest, stage: str, tier: str, prompt: str,
        payload: dict[str, Any], item: str = "") -> dict[str, Any]:
    """One model call, recorded into the trace with its completion verbatim.

    Every model call in the desk goes through here. That is what makes audit
    replay possible: the trace holds what the model said, in order, with the
    stage that asked, and nothing else needs to know about replay at all.
    """
    used = manifest.client.tier_for(tier)
    # Recorded on first use rather than declared up front, so the manifest
    # names the models that actually answered rather than the ones configured.
    manifest.record_model(ModelUse(id=manifest.client.model_for(tier),
                                   version=MODEL_VERSION, tier=used))
    text = manifest.client.complete(stage, tier, prompt, payload, item)
    manifest.trace.write("model_call", stage=stage, tier=used, text=text)
    return parse(text)


# ---------------------------------------------------------------------------
# The stages


@dataclass
class Corpus:
    """Records and the files they came from, so screening can record them."""

    records: list[dict[str, Any]]
    paths: list[Path]
    duplicates_removed: int


def retrieve_corpus(question) -> Corpus:
    """Script. Read, deduplicate on identifier, and count what was dropped.

    Deduplication is on identifiers, which is correct and which Build 11
    demonstrates is not sufficient. The count is reported rather than the
    absence of duplicates being assumed.
    """
    records, paths, seen = [], [], set()
    duplicates = 0
    for path in sorted(CORPUS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
        if payload["pmid"] in seen:
            duplicates += 1
            continue
        seen.add(payload["pmid"])
        records.append(payload)
        paths.append(path)
    return Corpus(records=records, paths=paths, duplicates_removed=duplicates)


def screen(corpus: Corpus, criteria: dict[str, Any],
           manifest: RunManifest) -> Screened:
    """Chain. One model call per record, no iteration, no tools.

    The chain cannot choose to do more work, which is the whole reason it is
    cheap enough to run on every record. Arithmetic is in Python: the count of
    verdicts is asserted against the count of records rather than asked for.
    """
    for path in corpus.paths:
        manifest.record_input(path)
    manifest.record_input(CRITERIA_FILE)
    manifest.criteria_version = criteria["version"]

    with timed(manifest, "abstract_screening", "chain, one model call per record"):
        verdicts = []
        for record in corpus.records:
            body = ask(
                manifest, "abstract_screening", "cheap",
                f"Screen PMID {record['pmid']} against criteria version "
                f"{criteria['version']}.",
                record, item=record["pmid"],
            )
            verdicts.append(Verdict(
                pmid=record["pmid"], decision=body["decision"],
                reason=body["reason"], criteria_version=criteria["version"],
                compounds=body.get("compounds", []),
            ))

    # Every record leaves a verdict. Counted in Python, as it has been since
    # Build 03.
    if len(verdicts) != len(corpus.records):
        raise DeskRefused(
            "records_unaccounted_for",
            f"{len(corpus.records)} records went in and {len(verdicts)} "
            "verdicts came out",
        )
    # Which records put each compound forward, so the shortlist can name its
    # evidence rather than asserting a compound arrived from somewhere.
    # Included records only: a flagged record has not yet said anything, and a
    # compound carried forward on the strength of an unresolved flag would be
    # a candidate whose evidence is a question nobody has answered.
    for verdict in verdicts:
        if verdict.decision == "include":
            for compound in verdict.compounds:
                manifest.evidence.setdefault(compound, []).append(verdict.pmid)

    return Screened(verdicts=verdicts, criteria_version=criteria["version"])


def triage_agent(ambiguous: list[Verdict], manifest: RunManifest) -> Resolved:
    """Agent loop. Fetch, read, decide, with a step cap on every record.

    This is one of the three loops, and it is a loop because it takes an
    action, reads what came back, and decides again. A record that exhausts
    the cap does not get a guessed verdict: it stays flagged, which is Build
    01's rule arriving for the last time.
    """
    resolved, steps_taken = [], {}
    with timed(manifest, "full_text_triage", "agent loop"):
        for verdict in ambiguous:
            body: dict[str, Any] = {}
            steps = 0
            payload = {"pmid": verdict.pmid, "step": 1,
                       "compounds": verdict.compounds}
            while steps < TRIAGE_STEP_CAP:
                steps += 1
                body = ask(
                    manifest, "full_text_triage", "workhorse",
                    f"Resolve flagged record {verdict.pmid}, step {steps}.",
                    payload, item=verdict.pmid,
                )
                if body.get("action") == "answer":
                    break
                payload = {**payload, "step": steps + 1,
                           "full_text": _full_text(verdict.pmid)}
            steps_taken[verdict.pmid] = steps

            if body.get("action") != "answer":
                # The cap was reached. No answer is invented from partial work.
                manifest.trace.write("triage_incomplete", pmid=verdict.pmid,
                                     steps=steps)
                resolved.append(verdict)
                continue
            settled = Verdict(
                pmid=verdict.pmid, decision=body["decision"],
                reason=body["reason"],
                criteria_version=verdict.criteria_version,
                compounds=body.get("compounds", verdict.compounds),
            )
            resolved.append(settled)
            if settled.decision == "include":
                for compound in settled.compounds:
                    manifest.evidence.setdefault(compound, []).append(
                        settled.pmid
                    )
    return Resolved(verdicts=resolved, steps_taken=steps_taken)


def _full_text(pmid: str) -> str:
    """The full text, standing in for a retrieval this build does not do.

    A real desk fetches this. Here it is the abstract plus a methods sentence
    from the same fixture, which is enough for the triage loop to have
    something the screening chain did not.
    """
    path = CORPUS_DIR / f"{pmid}.json"
    if not path.exists():
        return ""
    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
    return (
        f"{payload['abstract']} Methods: assays were performed in HepG2 "
        "cells maintained under standard conditions."
    )


def acquire_structures(resolved: Resolved, manifest: RunManifest) -> Targets:
    """Chain. Retrieve the structure record, check its provenance, prepare.

    No model call in this one. Structure retrieval is an API call and
    preparation is arithmetic, and a chain is a fixed sequence of steps rather
    than a sequence that necessarily contains a model.
    """
    question = manifest.question
    with timed(manifest, "structure_acquisition", "chain"):
        target = question.target
        path = STRUCTURES_DIR / f"{target}.json"
        if not path.exists():
            raise DeskRefused(
                "no_structure_record",
                f"no structure record for {target}. A docking run against a "
                "structure nobody recorded is a number with no provenance.",
            )
        manifest.record_input(path)
        record = StructureRecord(**json.loads(path.read_text(encoding="utf-8")))

        if record.source == "PREDICTED" and record.prediction_confidence is None:
            raise DeskRefused(
                "predicted_without_confidence",
                "a predicted structure with no pocket confidence is not "
                "usable evidence",
            )

        # Everything screening included, plus everything triage resolved into
        # an inclusion. A compound with no surviving record behind it is not
        # docked, however plausible its name.
        surviving = set(manifest.evidence) | set(resolved.compounds())
        ligands = {name: identifier
                   for name, identifier in question.compound_ligands.items()
                   if name in surviving}
        if not ligands:
            raise DeskRefused(
                "no_ligands",
                "screening named no compound that the registry can resolve to "
                "a ligand, so there is nothing to dock",
            )
    return Targets(records=[record], ligands=ligands)


def dock(targets: Targets, box_strategy: str,
         manifest: RunManifest) -> list[DockingResult]:
    """Script. Replay recorded engine output and parse it. No model anywhere.

    The box strategy is a parameter and it is recorded, because where the box
    went is the decision that most often makes two runs incomparable and it is
    almost never written down.
    """
    with timed(manifest, "docking", "script"):
        manifest.trace.write("docking_configured", box_strategy=box_strategy,
                             seed=SEED, exhaustiveness=EXHAUSTIVENESS,
                             engine=ENGINE)
        results = []
        for record in targets.records:
            for compound, ligand in sorted(targets.ligands.items()):
                path = VINA_DIR / f"{record.target}__{ligand}.pdbqt"
                if not path.exists():
                    raise DeskRefused(
                        "no_recorded_output",
                        f"no engine output for {record.target} and {ligand}",
                    )
                manifest.record_input(path)
                scores = [float(value) for value
                          in VINA_SCORE.findall(path.read_text(encoding="utf-8"))]
                if not scores:
                    raise DeskRefused("unparsable_output", f"{path.name}")
                results.append(DockingResult(
                    compound=compound, ligand_id=ligand, target=record.target,
                    poses=[Pose(rank=index, score=score)
                           for index, score in enumerate(scores, start=1)],
                    source=record.source, engine=ENGINE, seed=SEED,
                    exhaustiveness=EXHAUSTIVENESS,
                    evidence_pmids=manifest.evidence.get(compound, []),
                ))
    return results


def rank(poses: list[DockingResult],
         require_homogeneous: bool = True) -> Ranked:
    """Script with a gate. It refuses a mixed set rather than warning about it.

    Docking to as-is predicted models performed consistently worse than to
    experimental holo structures across twenty-two targets. A mixed set is
    defensible; a mixed set nobody recorded as mixed is not, so the caller has
    to say so explicitly.
    """
    sources = {result.source for result in poses}
    if require_homogeneous and len(sources) > 1:
        raise DeskRefused(
            "mixed_provenance",
            f"the result set mixes {sorted(sources)}. Pass "
            "require_homogeneous=False to rank it anyway, and the flag is "
            "written to the manifest so nobody can later say it was not known.",
        )

    ordered = sorted(poses, key=lambda result: (result.top_score,
                                                result.compound))
    return Ranked(
        candidates=[
            Candidate(
                position=index, compound=result.compound,
                ligand_id=result.ligand_id, target=result.target,
                score=result.top_score, cluster=result.cluster,
                source=result.source,
                evidence_pmids=result.evidence_pmids,
            )
            for index, result in enumerate(ordered, start=1)
        ],
        homogeneous=len(sources) == 1,
    )


def adapt_protocol(short: list[Candidate], target_line: str,
                   manifest: RunManifest) -> dict[str, Any]:
    """Agent loop. The frontier tier, because the volume is one.

    This is the stage where being wrong is expensive and there is exactly one
    of it per run, which is the case for spending on the best model available.
    Screening it at the same tier would multiply the bill by the size of the
    corpus and change nothing.
    """
    with timed(manifest, "protocol_adaptation", "agent loop"):
        manifest.record_input(DESIGN_FILE)
        manifest.design_ids.append("TMZ-NA-U87-001")
        payload = {"step": 1, "design_id": "TMZ-NA-U87-001",
                   "target_line": target_line,
                   "compounds": [candidate.compound for candidate in short]}
        body: dict[str, Any] = {}
        steps = 0
        while steps < PROTOCOL_STEP_CAP:
            steps += 1
            body = ask(
                manifest, "protocol_adaptation", "frontier",
                f"Adapt the design for {target_line}, step {steps}.",
                payload, item="protocol",
            )
            if body.get("action") == "answer":
                break
            payload = {**payload, "step": steps + 1}
        if body.get("action") != "answer":
            raise DeskRefused(
                "protocol_incomplete",
                "the protocol loop reached its step cap. There is no partial "
                "protocol, because a protocol somebody half wrote is worse "
                "than none.",
            )
    return body


def map_export(export_path: Path, manifest: RunManifest) -> dict[str, Any]:
    """Agent once, script thereafter. Not called by the printed spine.

    It is here because Table 12.1 names it and because it is the third stage
    that ever runs a loop. The first time an instrument is seen, an agent
    proposes a column mapping; every run after that replays the approved
    mapping with no model call at all, which is Build 05's whole argument.
    """
    cached = manifest.workspace / f"mapping_{export_path.stem}.json"
    if cached.exists():
        with timed(manifest, "export_mapping", "script"):
            manifest.mapping_ids.append(export_path.stem)
            return json.loads(cached.read_text(encoding="utf-8"))

    with timed(manifest, "export_mapping", "agent once, script thereafter"):
        manifest.mapping_ids.append(export_path.stem)
        body = ask(
            manifest, "export_mapping", "workhorse",
            f"Propose a column mapping for {export_path.name}.",
            {"instrument": export_path.stem}, item=export_path.stem,
        )
    cached.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    return body
