"""The last build: one orchestrating function calling deterministic stages.

``run_desk`` below is the printed listing, verbatim. Everything it calls lives
in ``stages.py`` and everything it decides is delegated to a person at one of
three checkpoints. It is fourteen lines of code and it is the argument of the
chapter.

## Not a coordinator delegating to specialist agents

There is no planner here, no router deciding which agent should handle a
record, and no agent explaining its findings to another agent. One study
measured multi-agent systems at four to two hundred and twenty times the tokens
of single-agent equivalents, and a rebuild found eighty per cent of a five
agent system's tokens going on agents describing their work to each other.

What survived is a script. Three of its nine stages run a model loop; the rest
are chains and scripts, and the reader is meant to count them. ``stages.py``
holds Table 12.1 as data and ``test_only_three_stages_are_agent_loops`` walks
it, so the count cannot drift without a test failing.

## Three names the printed spine references bare

``criteria_v3``, ``box_strategy`` and ``target_line`` appear in the listing as
bare names, so they are module-level here. That is forced by the listing rather
than chosen, and it has a consequence worth stating: the desk is configured for
one criteria version, one box strategy and one cell line, and a question asking
for something else is refused at the top of the run rather than silently
answered under the wrong configuration. ``_check_question_matches_configuration``
is where that happens.

The manifest carries the client, the approvals directory and the workspace,
because ``run_desk(question, manifest)`` takes nothing else. On reflection that
is the right shape: the things the run needs from its environment are exactly
the things that have to be recorded about it.

## What this system does not do

Table 12.3 is in ``refusals.py`` as six functions that raise. Grep for
``NotThisSystem``. The desk produces a shortlist, and a shortlist is where a
reader's work starts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from checkpoints import checkpoint
from models import Question, Shortlist
from provenance import RunManifest
from stages import (
    BUILDS,
    CRITERIA_FILE,
    DeskRefused,
    acquire_structures,
    adapt_protocol,
    dock,
    rank,
    retrieve_corpus,
    screen,
    triage_agent,
)

HERE = Path(__file__).resolve().parent

# The three run-level constants the printed spine names directly.
criteria_v3: dict[str, Any] = yaml.safe_load(
    CRITERIA_FILE.read_text(encoding="utf-8")
)

# Where the box went is the decision that most often makes two runs
# incomparable, and it is almost never recorded. It is a named constant here
# and it is written into the manifest by `dock`.
box_strategy: str = "cocrystal_ligand"

# The line protocols are adapted for. A question naming another line is
# refused rather than answered under this one.
target_line: str = "U87MG"


def run_desk(question: Question, manifest: RunManifest) -> Shortlist:
    corpus   = retrieve_corpus(question)              # script
    screened = screen(corpus, criteria_v3, manifest)  # chain + dual screen

    checkpoint("screening", screened, manifest)       # HUMAN 1

    ambiguous = screened.flagged
    resolved  = triage_agent(ambiguous, manifest)     # agent loop
    targets   = acquire_structures(resolved, manifest) # chain

    checkpoint("targets", targets, manifest)          # HUMAN 2

    poses   = dock(targets, box_strategy, manifest)   # script
    ranked  = rank(poses, require_homogeneous=True)   # script, refuses mixed
    short   = ranked.head(question.shortlist_n)

    checkpoint("shortlist", short, manifest)          # HUMAN 3

    protocol = adapt_protocol(short, target_line, manifest)  # agent loop
    return Shortlist(candidates=short, protocol=protocol,
                     manifest=manifest.finalise())


def _check_question_matches_configuration(question: Question) -> None:
    """Refuse a question this desk is not configured for.

    The alternative is answering it under the wrong criteria version or for
    the wrong cell line, which is the kind of mismatch that produces a
    perfectly formatted shortlist nobody can use.
    """
    if question.criteria_version != criteria_v3["version"]:
        raise DeskRefused(
            "criteria_version_mismatch",
            f"the question asks for criteria version "
            f"{question.criteria_version} and this desk is configured with "
            f"version {criteria_v3['version']}. Records screened under two "
            "versions are not comparable.",
        )
    if question.target_line != target_line:
        raise DeskRefused(
            "target_line_mismatch",
            f"the question names cell line {question.target_line!r} and this "
            f"desk adapts protocols for {target_line!r}.",
        )


def prepare(question: Question, manifest: RunManifest) -> None:
    """Everything that must be true before the spine starts.

    Kept out of ``run_desk`` because ``run_desk`` is the printed listing and a
    reader typing it from the page must get the printed listing.
    """
    _check_question_matches_configuration(question)
    manifest.question = question
    manifest.evidence = {}
    manifest.trace.write("run_started", question=question.question_id,
                         criteria_version=criteria_v3["version"],
                         box_strategy=box_strategy, target_line=target_line)


def run(question: Question, manifest: RunManifest) -> Shortlist:
    """Prepare, then run the printed spine, then finish the record.

    The outputs are written after ``run_desk`` returns, because the printed
    spine calls ``manifest.finalise()`` as its last expression and the
    shortlist does not exist until it has. So the manifest is finalised twice:
    once inside the spine, which is what the listing prints, and once here
    with the outputs in it. The second one is what lands on disk and what a
    replay compares against, and a manifest with no outputs in it would be a
    manifest that could not be replayed at all.
    """
    prepare(question, manifest)
    shortlist = run_desk(question, manifest)
    manifest.record_output("shortlist.json", [
        candidate.model_dump(mode="json") for candidate in shortlist.candidates
    ])
    manifest.record_output("protocol.json", shortlist.protocol)
    return shortlist.model_copy(update={"manifest": manifest.finalise()})


def load_question(path: str | Path | None = None) -> Question:
    return Question.load(path or HERE / "fixtures" / "question.yaml")


__all__ = [
    "BUILDS",
    "Question",
    "Shortlist",
    "box_strategy",
    "criteria_v3",
    "load_question",
    "prepare",
    "run",
    "run_desk",
    "target_line",
]


if __name__ == "__main__":  # pragma: no cover - a convenience, not a gate
    print(json.dumps(criteria_v3, indent=2))
