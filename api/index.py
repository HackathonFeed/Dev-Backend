"""Vercel serverless entrypoint — exports the FastAPI ASGI app."""

import sys
from pathlib import Path

# Vercel installs deps with pip (not uv). Ensure Backend/ is on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
__all__ = ["app"]
