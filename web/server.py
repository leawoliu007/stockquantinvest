#!/usr/bin/env python3
"""Production launcher: FastAPI backend + static frontend on a single port."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `web.backend.app` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.responses import HTMLResponse
from web.backend.app import app

project_root = Path(__file__).resolve().parent.parent
frontend_dist = project_root / "web" / "frontend" / "dist"
index_html = (frontend_dist / "index.html").read_bytes()

if not frontend_dist.exists():
    print("[quantinvest] Frontend not built. Run 'npm run build' in web/frontend/")
    sys.exit(1)

# Serve index.html with no-cache so browser always gets latest JS hash reference
@app.get("/", include_in_schema=False)
async def serve_spa_root():
    from starlette.responses import Response
    return Response(index_html.replace(
        '<link rel="modulepreload"',
        '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">\n<link rel="modulepreload"'
    ), media_type="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

# Mount static assets (JS/CSS/images) — html=True provides SPA fallback for other paths
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8765)
