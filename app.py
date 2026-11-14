"""Serve the Strava wax checker UI and a coaching data API for agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from garmin_coach import fetch_coach_snapshot

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = FastAPI(
    title="Strava Wax Checker + Coach API",
    description=(
        "Static bike wax tracker UI plus GET /api/coach, which returns a "
        "Garmin Personal API snapshot shaped for training-coach agents."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/coach")
def coach(
    request: Request,
    days: int = Query(14, ge=1, le=92, description="Last N days including today"),
    start: str | None = Query(None, description="Inclusive start YYYY-MM-DD"),
    end: str | None = Query(None, description="Inclusive end YYYY-MM-DD"),
    max_activities: int = Query(200, ge=1, le=500),
    x_garmin_api_key: str | None = Header(default=None, alias="X-Garmin-Api-Key"),
) -> dict[str, Any]:
    """Return Garmin training/recovery data for coaching agents (schema 1.0)."""
    api_key = (
        (x_garmin_api_key or "").strip()
        or os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    )
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "No Garmin Personal API key. Pass X-Garmin-Api-Key from the page "
                "or set GARMIN_PERSONAL_API_KEY in the server environment."
            ),
        )
    try:
        snap = fetch_coach_snapshot(
            days=days,
            start=start,
            end=end,
            max_activities=max_activities,
            api_key=api_key,
        )
        # Keep a static copy for GitHub Pages fallback when running locally.
        try:
            out = ROOT / "coach.json"
            import json

            out.write_text(json.dumps(snap, indent=2, default=str) + "\n", encoding="utf-8")
        except OSError:
            pass
        return snap
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Garmin fetch failed: {exc}") from exc


# Static site (existing GitHub Pages app). API routes are registered above.
STATIC_FILES = {
    "index.html",
    "style.css",
    "script.js",
    "garmin.js",
    "config.js",
    "coach.json",
    "package.json",
    "README.md",
}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/{name}")
def static_file(name: str) -> FileResponse:
    if name not in STATIC_FILES or not (ROOT / name).is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(ROOT / name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
