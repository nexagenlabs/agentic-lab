"""Record the three approvals the tests run against, and the known answer.

The output is committed, so the gate runs unattended. This generator is
committed with it because the approvals bind to a hash of what was approved,
and a reader should be able to see how that binding was produced rather than
take three opaque digests on trust.

## Why a generator is needed at all

``checkpoints.checkpoint`` refuses an approval whose ``reviewed_sha256`` does
not match the artefact in front of it. That is the point of the mechanism: an
approval that survives a change to the thing it approved is not a record of
anybody's judgement. The consequence is that the committed approvals have to be
regenerated whenever a stage changes what it produces, and doing that by hand
would mean pasting digests, which nobody would check.

So this file runs the desk with the checkpoints in recording mode, capturing
what each one was shown and signing it in one place. Run it from the build
folder:

    python fixtures/make_checkpoints.py

The approver name and the notes are fabricated, and say so.

## The known answer is not generated here

``known_answer/shortlist.json`` is written by hand and this file does not
touch it. That is deliberate. A known answer produced by the system it checks
is a tautology, and `test_shortlist_matches_known_answer` would then be
asserting that the desk agrees with itself.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import checkpoints as checkpoints_module
import desk
from checkpoints import record_approval_for
from provenance import RunManifest
from stub_client import TieredClient

APPROVER = "S. Bramall"
WHEN = datetime(2026, 8, 30, 9, 30, tzinfo=timezone.utc)

NOTES = {
    "screening": (
        "Read the twelve inclusions and the three flags. The exclusions I "
        "spot-checked were all publication type or no named model. Content "
        "with what is being carried forward."
    ),
    "targets": (
        "One experimental holo structure, provenance recorded, and the "
        "ligand map is the alphabetical assignment declared in the question. "
        "Happy to spend the compute."
    ),
    "shortlist": (
        "Three compounds, ranked by top docking score, each with the records "
        "behind it. I do not think this answers the question that was asked, "
        "and I have said so in the handoff, but the shortlist is a correct "
        "account of what the corpus supports."
    ),
}


def main() -> None:
    """Run the desk once with the checkpoints recording rather than blocking."""
    workspace = Path(tempfile.mkdtemp(prefix="desk-approvals-"))
    approvals = HERE / "checkpoints"
    if approvals.exists():
        shutil.rmtree(approvals)
    approvals.mkdir(parents=True)

    signed: list[str] = []
    real_checkpoint = checkpoints_module.checkpoint

    def recording_checkpoint(name, payload, manifest):
        record_approval_for(name, payload, APPROVER, NOTES[name], approvals,
                            when=WHEN)
        signed.append(name)
        return real_checkpoint(name, payload, manifest)

    # Patched in the module the spine imported it from, so the desk runs its
    # own code path rather than a copy of it.
    desk.checkpoint = recording_checkpoint
    try:
        manifest = RunManifest(
            run_id="desk-approvals", root=desk.HERE.parent.parent,
            client=TieredClient(), approvals_dir=approvals,
            workspace=workspace,
        )
        question = desk.load_question()
        shortlist = desk.run(question, manifest)
    finally:
        desk.checkpoint = real_checkpoint

    print(f"signed {len(signed)} checkpoints: {', '.join(signed)}")
    for name in signed:
        print(f"  {approvals / name}.json")
    print(f"shortlist: {', '.join(shortlist.compounds())}")
    print("known_answer/shortlist.json is written by hand and was not touched")
    shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
