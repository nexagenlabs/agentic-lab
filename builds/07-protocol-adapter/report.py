"""The diff, written out against a reporting standard.

The categories are the Good In Vitro Reporting Standards headings. Mapping the
adaptation onto them turns a list of parameters into an answer to a question a
reader actually has, which is: what did this protocol never tell me?

So the report never omits a category. A heading with nothing under it is the
most informative line in the document, and a report that quietly drops its
empty sections is a report that reads as complete when it is not.
"""

from __future__ import annotations

from pathlib import Path

from adapt import AdaptationRun

# Which Table 6.2 parameters land under which reporting category. Two
# categories hold none, and they are printed anyway.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "Cell source and identity": (),
    "Quality control": ("passage_number_range",),
    "Materials": ("solvent_tolerance", "readout_chemistry"),
    "Culture conditions": ("serum_concentration", "seeding_density"),
    "Design": ("incubation_to_endpoint",),
    "Analysis": (),
    "Data availability": (),
}

READABLE = {
    "seeding_density": "seeding density",
    "incubation_to_endpoint": "incubation to endpoint",
    "solvent_tolerance": "solvent tolerance",
    "passage_number_range": "passage number range",
    "serum_concentration": "serum concentration",
    "readout_chemistry": "readout chemistry",
}


def empty_categories(run: AdaptationRun) -> list[str]:
    """Categories this source protocol leaves with nothing in them."""
    silent = set(run.adaptation.not_stated_in_source)
    empty = []
    for category, parameters in CATEGORIES.items():
        if category == "Cell source and identity":
            if not run.protocol.declares_identity:
                empty.append(category)
        elif not parameters or set(parameters) <= silent:
            empty.append(category)
    return empty


def _identity_lines(run: AdaptationRun) -> list[str]:
    rrid = run.protocol.cell_line_rrid
    lines = [
        f"- Source line: {run.protocol.cell_line}"
        + (f", {rrid}" if rrid else ", **no RRID stated in the source**"),
        (f"- Target line: {run.target.name}, {run.target.rrid}, doubling time "
         f"{run.target.doubling_time_h:g} h"),
        f"- Source DOI: {run.protocol.doi}",
    ]
    if not rrid:
        lines.append(
            "- The source names its line without an identifier, so the line "
            "the work was done in cannot be checked. That is not a defect in "
            "this adaptation, it is a limit on what the adaptation can mean."
        )
    return lines


def _parameter_line(run: AdaptationRun, parameter: str) -> str:
    adaptation = run.adaptation
    name = READABLE[parameter]
    for change in adaptation.changed:
        if change.parameter == parameter:
            return (f"- **{name}**: changed, {change.source_value} to "
                    f"{change.adapted_value}. {change.rationale} "
                    f"(confidence: {change.confidence})")
    if parameter in adaptation.carried_over_unchanged:
        stated = run.readings[parameter].value
        return f"- **{name}**: carried over unchanged, {stated}."
    if parameter in adaptation.requires_human_decision:
        return (f"- **{name}**: **requires a human decision.** The adapter "
                "will not settle this one on your behalf.")
    return (f"- **{name}**: **not stated in the source.** Nothing was "
            "substituted for it.")


def render_report(run: AdaptationRun) -> str:
    """The adaptation as markdown, organised by reporting category."""
    adaptation = run.adaptation
    empty = empty_categories(run)

    out = [
        f"# Adaptation: {run.protocol.cell_line} to {run.target.name}",
        "",
        "The adapted protocol is not the product of this build. This diff is.",
        "Read the empty categories first.",
        "",
        "## Summary",
        "",
        f"- Changed: {len(adaptation.changed)}",
        f"- Carried over unchanged: {len(adaptation.carried_over_unchanged)}",
        f"- Not stated in the source: {len(adaptation.not_stated_in_source)}",
        f"- Requires a human decision: {len(adaptation.requires_human_decision)}",
        "",
        "## Categories the source protocol leaves empty",
        "",
    ]
    if empty:
        out.append(
            "These are printed because they are empty, not despite it. An "
            "absent category is the useful output."
        )
        out.append("")
        for category in empty:
            out.append(f"- **{category}**")
    else:
        out.append("None. Every reporting category has something under it.")
    out.append("")

    for category, parameters in CATEGORIES.items():
        out.append(f"## {category}")
        out.append("")
        if category == "Cell source and identity":
            out.extend(_identity_lines(run))
        elif parameters:
            out.extend(_parameter_line(run, p) for p in parameters)
        else:
            out.append(
                "Nothing in this adaptation falls under this category, and "
                "the source protocol states nothing that would. Empty, and "
                "named as empty."
            )
        out.append("")

    if run.rejected_claims:
        out.append("## Claims the adapter refused")
        out.append("")
        out.append(
            "Each of these was reported by the extraction step and did not "
            "survive verification against the protocol text."
        )
        out.append("")
        for claim in run.rejected_claims:
            out.append(
                f"- **{READABLE.get(claim['parameter'], claim['parameter'])}**: "
                f"claimed {claim['claimed_value']!r} on the evidence "
                f"{claim['evidence']!r}. Refused, code `{claim['code']}`."
            )
        out.append("")

    return "\n".join(out)


def write_report(run: AdaptationRun, path: str | Path) -> Path:
    """Write ``adaptation_report.md`` and return where it went."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(run), encoding="utf-8")
    return path
