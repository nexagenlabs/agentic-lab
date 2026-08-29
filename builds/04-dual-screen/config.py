"""The one place in this build that names a model, or a seed.

Two screens means two model identifiers. They are separate settings rather
than one setting used twice, because the whole point of the second screen is
that it is not the first one.

The gold set seed lives here too. A seed buried at a call site is a seed
nobody records, and a gold set that cannot be reconstructed is not a
reference standard.
"""

import os

SCREEN_A_MODEL = os.environ.get("SCREEN_A_MODEL", "claude-sonnet-5")
SCREEN_B_MODEL = os.environ.get("SCREEN_B_MODEL", "claude-opus-5")

# Recorded, not arbitrary. Changing it changes which negatives are drawn, so
# it belongs in version control and in the emitted report.
GOLD_SEED = 20260429

# How many negatives join the enriched categories. Eight, per the spec.
GOLD_NEGATIVES = 8
