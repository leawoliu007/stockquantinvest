#!/usr/bin/env python3
"""Production launcher: FastAPI backend + static frontend on a single port."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `web.backend.app` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.staticfiles import StaticFiles
from web.backend.app import app

project_root = Path(__file__).resolve().parent.parent
frontend_dist = project_root / "web" / "frontend" / "dist"

if not frontend_dist.exists():
    print("[quantinvest] Frontend not built. Run 'npm run build' in web/frontend/")
    sys.exit(1)

app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8000)
