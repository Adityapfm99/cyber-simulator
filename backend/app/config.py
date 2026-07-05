"""Runtime configuration.

Defaults are safe for local development. In a real air-gapped deployment these
would come from a sealed config file on the institution's own hardware.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.environ.get("CYBERSIM_DB", f"sqlite:///{DATA_DIR / 'cybersim.db'}")

# Token signing secret. Regenerated per deployment in production.
SECRET_KEY = os.environ.get("CYBERSIM_SECRET", "dev-only-not-for-production-change-me")
TOKEN_TTL_SECONDS = 8 * 60 * 60  # one training shift

SCENARIO_TEMPLATE_DIR = BASE_DIR / "scenario_templates"

# §4 Guardrail: target incident-response times (seconds). Exceeding these is
# flagged as an SOP gap in the After-Action Review.
TARGET_TTD = 300   # Time to Detect
TARGET_TTT = 600   # Time to Triage
TARGET_TTC = 1800  # Time to Contain
TARGET_TTR = 3600  # Time to Recover
