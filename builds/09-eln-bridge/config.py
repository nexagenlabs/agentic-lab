"""The one place in this build that names a model.

MODELS.md holds the current names and a dated changelog. Changing the model
this build runs against is an environment variable, not an edit.
"""

import os

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")

# Stamped onto every proposal and every ledger entry. The notebook records who
# wrote an entry, and "an agent" is not an answer anybody can audit six months
# later. A version that never moves is a version nobody can correlate with a
# change in behaviour.
MODEL_VERSION = os.environ.get("AGENT_MODEL_VERSION", "2026-08-01")
