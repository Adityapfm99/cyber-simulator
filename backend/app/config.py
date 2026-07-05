"""Runtime configuration.

Defaults are safe for local development. In a real air-gapped deployment these
would come from a sealed config file on the institution's own hardware.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
try:
    DATA_DIR.mkdir(exist_ok=True)
except OSError:
    # Serverless filesystems (e.g. Vercel) are read-only outside /tmp. When we
    # can't create a local data dir we're running against a hosted DB anyway.
    DATA_DIR = Path("/tmp")

# Database URL resolution order:
#   CYBERSIM_DB  → explicit override
#   DATABASE_URL / POSTGRES_URL → provided by hosts like Vercel Postgres / Neon
#   otherwise    → local SQLite file (development)
DATABASE_URL = (
    os.environ.get("CYBERSIM_DB")
    or os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or f"sqlite:///{DATA_DIR / 'cybersim.db'}"
)

# Token signing secret. Regenerated per deployment in production.
SECRET_KEY = os.environ.get("CYBERSIM_SECRET", "dev-only-not-for-production-change-me")
TOKEN_TTL_SECONDS = 8 * 60 * 60  # one training shift

SCENARIO_TEMPLATE_DIR = BASE_DIR / "scenario_templates"

# Run the always-on background simulation loop? True for a normal server; set
# CYBERSIM_BACKGROUND=0 on serverless (no long-lived process), where baseline
# traffic is instead generated lazily on demand (see soc.lazy_fill).
RUN_BACKGROUND = os.environ.get("CYBERSIM_BACKGROUND", "1") != "0"

# Seed demo users automatically on startup if the DB has none.
AUTO_SEED = os.environ.get("CYBERSIM_AUTOSEED", "1") != "0"

# §4 Guardrail: target incident-response times (seconds). Exceeding these is
# flagged as an SOP gap in the After-Action Review.
TARGET_TTD = 300   # Time to Detect
TARGET_TTT = 600   # Time to Triage
TARGET_TTC = 1800  # Time to Contain
TARGET_TTR = 3600  # Time to Recover
