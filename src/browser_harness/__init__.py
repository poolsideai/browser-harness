"""Browser Harness core package."""

import os

os.environ["BH_TELEMETRY"] = "0"
os.environ.pop("BU_AUTOSPAWN", None)
