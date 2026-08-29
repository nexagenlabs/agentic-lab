"""The one place in this build that names a model.

MODELS.md holds the current names and a dated changelog. Changing the model
this build runs against is an environment variable, not an edit.
"""

import os

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
