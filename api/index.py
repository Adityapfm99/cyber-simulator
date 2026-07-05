"""Vercel serverless entry point.

Vercel's Python runtime serves the module-level ``app`` (an ASGI application).
We add the ``backend`` directory to the import path and expose the FastAPI app.

Serverless has no long-lived process, so we force the background ticker off;
baseline SOC traffic is generated lazily on each poll instead (see
``app.soc.lazy_fill``). Set ``DATABASE_URL`` (Vercel Postgres / Neon) so state
persists — the ephemeral filesystem cannot hold a SQLite file.
"""
import os
import sys
from pathlib import Path

# Make the `app` package (under ../backend) importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# No always-on loop in serverless; generate traffic on demand.
os.environ.setdefault("CYBERSIM_BACKGROUND", "0")

from app.main import app  # noqa: E402  (import after sys.path/env setup)

# Ensure tables + demo users exist on a cold start (idempotent).
try:
    from app.main import _ensure_ready

    _ensure_ready()
except Exception as exc:  # pragma: no cover - never block cold start
    print(f"[vercel] warm-up skipped: {exc}")
