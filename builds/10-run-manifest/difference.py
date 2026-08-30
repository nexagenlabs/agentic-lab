"""When a replay disagrees: which of three things moved?

A report that says "outputs differ" is not useful. It is the beginning of two
days of work, and the two days are spent rediscovering the same three
candidates every time. A report that says "four external response hashes
changed and nothing else did" is an answer.

So the report has a section per candidate, always, in the same order, whether
or not anything moved in it. The empty sections are as load-bearing as the full
ones: "the code did not change" is what makes "the world did" believable, and a
report that printed only what moved would leave a reader wondering what was
checked.

    CODE    does git_commit differ, was either tree dirty, does the
            lockfile hash differ?
    MODEL   does any model version in the manifest differ from what is
            configured now, or from the other run?
    WORLD   does any input hash or external response hash differ, and has
            the corpus snapshot moved?

The last thing the report does is the one the chapter argues for hardest: it
distinguishes a divergence that is explained from one that is not. Four
external hashes moving and six inclusions changing is not a failure. Nobody was
wrong, the upstream records were revised, and both runs are correct accounts of
different worlds. Reporting that as a failure teaches people to ignore the
report. Outputs differing with nothing moved anywhere is the case that deserves
alarm, and it is the case this build calls ``unexplained_divergence``.
"""

from __future__ import annotations

from typing import Any

from models import RunManifest
from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    changed: bool
    findings: list[str] = Field(default_factory=list)
    unchanged_note: str = ""

    def render(self) -> str:
        head = f"{self.name.upper()}: {'changed' if self.changed else 'unchanged'}"
        body = self.findings if self.changed else [self.unchanged_note]
        return "\n".join([head] + [f"  {line}" for line in body if line])


class DifferenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    baseline_run: str
    other_run: str
    headline: str
    outputs_differ: list[str] = Field(default_factory=list)
    code: Section
    model: Section
    world: Section
    external_changed: list[dict[str, str]] = Field(default_factory=list)
    attribution: str = ""
    code_and_model_unchanged: bool = False
    is_failure: bool = False
    verdict: str = ""

    def render(self, include_headline: bool = True) -> str:
        """The report. The headline goes first, because a reproduction claim
        with no stated conditions is not a claim; the caller may suppress it
        only when it has just printed the same sentence itself."""
        lines = ([self.headline, ""] if include_headline else []) + [
            f"DIFFERENCE REPORT: {self.baseline_run} against {self.other_run}",
            (f"Outputs differing: {len(self.outputs_differ)} "
             f"({', '.join(self.outputs_differ) or 'none'})"),
            "",
            self.code.render(),
            "",
            self.model.render(),
            "",
            self.world.render(),
            "",
            f"ATTRIBUTION: {self.attribution}",
            self.verdict,
        ]
        return "\n".join(lines)


def _output_map(manifest: RunManifest) -> dict[str, str]:
    return {record.path: record.sha256 for record in manifest.outputs}


def _input_map(manifest: RunManifest) -> dict[str, str]:
    return {record.path: record.sha256 for record in manifest.inputs}


def _call_map(manifest: RunManifest) -> dict[str, str]:
    return {call.identifier: call.response_sha256
            for call in manifest.external_calls}


def _model_map(manifest: RunManifest) -> dict[str, str]:
    return {use.id: use.version for use in manifest.models}


def difference_report(baseline: RunManifest, other: RunManifest,
                      configured_models: dict[str, str] | None = None
                      ) -> DifferenceReport:
    """Compare two runs, and say which of the three candidates moved."""
    outputs_a, outputs_b = _output_map(baseline), _output_map(other)
    differing = sorted(
        path for path in set(outputs_a) | set(outputs_b)
        if outputs_a.get(path) != outputs_b.get(path)
    )

    code = _code_section(baseline, other)
    model = _model_section(baseline, other, configured_models or {})
    world, external_changed = _world_section(baseline, other)

    moved = [section.name for section in (code, model, world) if section.changed]
    if not differing and not moved:
        attribution = "nothing moved, and the outputs agree"
        verdict = "The run reproduces."
        is_failure = False
    elif differing and not moved:
        attribution = (
            "unexplained. The outputs differ and the code, the model and the "
            "world all hash the same"
        )
        verdict = (
            "This is the case that deserves alarm. Two runs of the same code "
            "over the same corpus with the same model produced different "
            "outputs, so something that determines the result is not in the "
            "manifest. Look for an unrecorded seed, an unstable sort, a "
            "dictionary order, or a timestamp inside an output."
        )
        is_failure = True
    else:
        attribution = "the " + " and the ".join(moved) + " moved"
        verdict = _verdict_for(moved, differing, external_changed)
        # Something moved, so the difference is accounted for. Only an
        # unexplained divergence is a failure here, and saying otherwise is how
        # a report trains people to stop reading it.
        is_failure = False

    return DifferenceReport(
        baseline_run=baseline.run_id,
        other_run=other.run_id,
        headline=other.describe(),
        outputs_differ=differing,
        code=code, model=model, world=world,
        external_changed=external_changed,
        attribution=attribution,
        code_and_model_unchanged=not code.changed and not model.changed,
        is_failure=is_failure,
        verdict=verdict,
    )


def _verdict_for(moved: list[str], differing: list[str],
                 external_changed: list[dict[str, str]]) -> str:
    if moved == ["world"]:
        return (
            f"This is not a failure. {len(external_changed)} external response "
            "hash(es) changed, the code and the model did not change, and the "
            "difference in the outputs follows from upstream records having "
            "been revised between the two runs. Neither run is wrong. They are "
            "correct accounts of two different states of the world, and the "
            "corpus snapshot identifier is what names the difference between "
            "them."
        )
    if "code" in moved:
        return (
            "The code moved, so this is not a reproduction. Compare the "
            "commits before looking anywhere else; a code change explains an "
            "output change and nothing further needs to be hypothesised."
        )
    if "model" in moved:
        return (
            "The model version moved. This is a different experiment rather "
            "than a failed reproduction, and audit replay is the tool that "
            "still answers the original question."
        )
    return "Reviewed."


def _code_section(baseline: RunManifest, other: RunManifest) -> Section:
    findings = []
    if baseline.git_commit != other.git_commit:
        findings.append(
            f"git_commit {baseline.git_commit} to {other.git_commit}"
        )
    if baseline.lockfile_sha256 != other.lockfile_sha256:
        findings.append(
            f"lockfile_sha256 {baseline.lockfile_sha256[:16]} to "
            f"{other.lockfile_sha256[:16]}"
        )
    # A dirty tree is disclosed on both sides whether or not anything differs,
    # because the commit hash alone does not identify the code that ran.
    dirty = [manifest.run_id for manifest in (baseline, other)
             if manifest.git_dirty]
    if dirty:
        findings.append(
            f"uncommitted changes present in: {', '.join(dirty)}. The commit "
            "hash does not identify the code that ran."
        )
    return Section(
        name="code", changed=bool(findings), findings=findings,
        unchanged_note=(
            f"same commit {baseline.git_commit}, same lockfile, "
            f"both trees clean"
        ),
    )


def _model_section(baseline: RunManifest, other: RunManifest,
                   configured: dict[str, str]) -> Section:
    findings = []
    models_a, models_b = _model_map(baseline), _model_map(other)
    for name in sorted(set(models_a) | set(models_b)):
        if models_a.get(name) != models_b.get(name):
            findings.append(
                f"{name} {models_a.get(name, 'absent')} to "
                f"{models_b.get(name, 'absent')}"
            )
    for name, version in sorted(configured.items()):
        recorded = models_b.get(name)
        if recorded and recorded != version:
            findings.append(
                f"{name} ran at {recorded} and this machine is configured "
                f"for {version}"
            )
    described = ", ".join(f"{name}@{version}"
                          for name, version in sorted(models_b.items()))
    return Section(
        name="model", changed=bool(findings), findings=findings,
        unchanged_note=f"same versions in both runs: {described or 'none'}",
    )


def _world_section(baseline: RunManifest, other: RunManifest
                   ) -> tuple[Section, list[dict[str, str]]]:
    findings = []
    inputs_a, inputs_b = _input_map(baseline), _input_map(other)
    for path in sorted(set(inputs_a) | set(inputs_b)):
        if inputs_a.get(path) != inputs_b.get(path):
            findings.append(
                f"input {path}: {(inputs_a.get(path) or 'absent')[:16]} to "
                f"{(inputs_b.get(path) or 'absent')[:16]}"
            )

    calls_a, calls_b = _call_map(baseline), _call_map(other)
    external_changed = []
    for identifier in sorted(set(calls_a) | set(calls_b)):
        before, after = calls_a.get(identifier), calls_b.get(identifier)
        if before != after:
            external_changed.append({
                "identifier": identifier,
                "before": before or "absent",
                "after": after or "absent",
            })
    if external_changed:
        findings.append(
            f"external response hashes changed: {len(external_changed)}"
        )
        findings.extend(
            f"  {entry['identifier']}: {entry['before'][:16]} to "
            f"{entry['after'][:16]}"
            for entry in external_changed
        )

    if baseline.corpus_snapshot_id != other.corpus_snapshot_id:
        findings.append(
            f"corpus_snapshot_id {baseline.corpus_snapshot_id[:16]} to "
            f"{other.corpus_snapshot_id[:16]}"
        )

    return Section(
        name="world", changed=bool(findings), findings=findings,
        unchanged_note=(
            f"{len(inputs_b)} input(s) and {len(calls_b)} external call(s) "
            f"hash the same, corpus snapshot "
            f"{other.corpus_snapshot_id[:16]} unchanged"
        ),
    ), external_changed


def summarise(report: DifferenceReport) -> dict[str, Any]:
    """The report as structure, for a trace or a dashboard."""
    return {
        "status": "FAILED" if report.is_failure else "EXPLAINED",
        "code": ("unexplained_divergence" if report.is_failure
                 else "difference_attributed"),
        "attribution": report.attribution,
        "outputs_differ": report.outputs_differ,
        "external_changed": [entry["identifier"]
                             for entry in report.external_changed],
        "code_and_model_unchanged": report.code_and_model_unchanged,
    }
