"""Table 12.2: what the run cost, measured rather than estimated.

Two kinds of number live here and they are labelled differently, because
conflating them is how a cost model stops being checkable.

**Measured.** Wall clock per stage, model calls per stage, tokens by tier.
These are counted by ``stages.timed`` while the run happens. They are the wall
clock of *this* run on *this* machine, and with recorded fixtures standing in
for a docking engine and a model API they are small. The accounting says so
rather than substituting the figure a real run would produce. The chapter's
forty minutes of compute is a real run against a real engine and a real API;
this is not that run, and printing forty minutes here would be an estimate
wearing a measurement's clothes.

**Declared.** Human minutes per checkpoint. Nothing can measure how long
somebody spent looking at a diff, so these are markers saying attention is
required here, with the chapter's figures attached, and every table that
prints them says "declared".

## The line the chapter cares about

The largest single block of human time is the ninety minutes at the shortlist
checkpoint, and nothing automates it. It equals the other two checkpoints put
together and it dwarfs the compute. An accounting that reported
only tokens would show a run that cost very little and hide the three hours,
so the human column comes first in the table and the totals are reported
separately rather than added together. Minutes and tokens do not add.
"""

from __future__ import annotations

from pathlib import Path

from checkpoints import CHECKPOINTS
from config import RELATIVE_COST_PER_1K
from provenance import RunManifest, StageCost
from stages import TABLE_12_1


def stage_level(name: str) -> str:
    for stage in TABLE_12_1:
        if stage.name == name:
            return stage.level
    return "unrecorded"


def declared_human_minutes() -> dict[str, int]:
    """Which stage each checkpoint sits after, and the time it is given."""
    # Keyed by the stage each checkpoint gates, which is the stage that
    # cannot start until somebody has looked. Ranking is a script the printed
    # spine calls without the manifest, so it records no stage of its own; the
    # ninety minutes at the shortlist is attributed to the stage it blocks.
    return {
        "abstract_screening": CHECKPOINTS["screening"]["declared_minutes"],
        "structure_acquisition": CHECKPOINTS["targets"]["declared_minutes"],
        "protocol_adaptation": CHECKPOINTS["shortlist"]["declared_minutes"],
    }


def relative_cost(tokens: dict[str, int]) -> float:
    return round(sum(count / 1000.0 * RELATIVE_COST_PER_1K[tier]
                     for tier, count in tokens.items()), 4)


def totals(stages: list[StageCost]) -> dict[str, float | int]:
    tokens: dict[str, int] = {}
    for stage in stages:
        for tier, count in stage.tokens.items():
            tokens[tier] = tokens.get(tier, 0) + count
    declared = declared_human_minutes()
    return {
        "seconds": round(sum(stage.seconds for stage in stages), 4),
        "model_calls": sum(stage.model_calls for stage in stages),
        "tokens": tokens,
        "total_tokens": sum(tokens.values()),
        "relative_cost": relative_cost(tokens),
        "declared_human_minutes": sum(declared.values()),
    }


def render(manifest: RunManifest) -> str:
    """``run_accounting.md``, in the shape of Table 12.2."""
    declared = declared_human_minutes()
    summed = totals(manifest.stages)

    lines = [
        f"# Run accounting: {manifest.run_id}",
        "",
        manifest.describe(),
        "",
        ("Human minutes are **declared**, not measured: nothing can time "
         "how long somebody spent looking at a diff. Everything else is "
         "measured from this run on this machine, where recorded fixtures "
         "stand in for a docking engine and a model API, so the compute "
         "figures are small and are not the chapter's forty minutes."),
        "",
        ("| Stage | Level | Human (declared) | Model calls | Tokens | "
         "Relative cost | Seconds |"),
        "|---|---|---|---|---|---|---|",
    ]

    for stage in manifest.stages:
        minutes = declared.get(stage.stage, 0)
        human = f"**{minutes} min**" if minutes else "-"
        tokens = (", ".join(f"{tier} {count}"
                            for tier, count in sorted(stage.tokens.items()))
                  or "-")
        lines.append(
            f"| {stage.stage} | {stage.level} | {human} | "
            f"{stage.model_calls} | {tokens} | "
            f"{relative_cost(stage.tokens) or '-'} | {stage.seconds} |"
        )

    lines += [
        "",
        (f"**Measured compute.** {summed['model_calls']} model calls, "
         f"{summed['total_tokens']} tokens, "
         f"{summed['relative_cost']} relative cost units, "
         f"{summed['seconds']} seconds of wall clock."),
        "",
        (f"**Declared human attention.** "
         f"{summed['declared_human_minutes']} minutes, across three "
         "checkpoints."),
        "",
        ("The two are reported separately and never added, because minutes "
         "and tokens do not add."),
        "",
        "## Where the human time goes",
        "",
        "| Checkpoint | Declared minutes | What it gates |",
        "|---|---|---|",
    ]
    for name, body in CHECKPOINTS.items():
        lines.append(
            f"| {name} | {body['declared_minutes']} | {body['narrowing']} |"
        )

    shortlist_minutes = CHECKPOINTS["shortlist"]["declared_minutes"]
    other = sum(body["declared_minutes"] for name, body in CHECKPOINTS.items()
                if name != "shortlist")
    lines += [
        "",
        (f"The shortlist checkpoint is {shortlist_minutes} minutes, the "
         f"largest single block of human time in the run and equal to the "
         f"other two checkpoints ({other} minutes) put together. Nothing in "
         "this repository automates any of it. That is the honest accounting "
         "the chapter asks for: the compute is the cheap part, and the "
         "expensive part is somebody looking at three compounds and "
         "deciding whether any of them is worth a bench."),
    ]
    return "\n".join(lines) + "\n"


def write(manifest: RunManifest, path: str | Path | None = None) -> Path:
    target = Path(path) if path else manifest.workspace / "run_accounting.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(manifest), encoding="utf-8", newline="\n")
    return target
