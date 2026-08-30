"""The one place in this build that names a model, and it names three.

Three tiers, because the chapter's argument about cost is that routing is real
work rather than a slogan. Per-record screening runs on the cheap tier because
it is a classification with a rubric; the two agent loops run on the workhorse
tier; the frontier tier is reserved for protocol adaptation, which is the one
stage where being wrong is expensive and the volume is one.

Changing any of them is an environment variable, not an edit. MODELS.md holds
the current names and a dated changelog.
"""

import os

CHEAP = os.environ.get("AGENT_MODEL_CHEAP", "claude-haiku-4-5")
WORKHORSE = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
FRONTIER = os.environ.get("AGENT_MODEL_FRONTIER", "claude-opus-5")

MODEL_VERSION = os.environ.get("AGENT_MODEL_VERSION", "2026-08-01")

TIERS = {"cheap": CHEAP, "workhorse": WORKHORSE, "frontier": FRONTIER}

# Relative cost per thousand tokens. Ratios rather than currency, because a
# price in dollars is out of date before the chapter is printed and a reader
# in another country never had that price anyway. The ratios are what the
# routing argument depends on.
RELATIVE_COST_PER_1K = {"cheap": 1.0, "workhorse": 5.0, "frontier": 25.0}
