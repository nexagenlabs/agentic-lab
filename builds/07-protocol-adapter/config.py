"""The one place in this build that names a model.

Read from the environment with a default, so a reader changes it without
editing source and a run records which model actually answered.
"""

import os

AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
