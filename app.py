"""Serve the Strava wax checker UI and a coaching data API for agents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from garmin_coach import fetch_coach_snapshot, to_agent_markdown

ROOT = Path(__file__).resolve().parent
AGENT_JSON_PATH = ROOT / "agent.json"
AGENT_MD_PATH = ROOT / "agent.md"
AGENT_HTML_PATH = ROOT / "agent" / "index.html"
COACH_JSON_PATH = ROOT / "coach.json"
load_dotenv(ROOT / ".env")

app = FastAPI(
    title="Strava Wax Checker + Coach API",
    description=(
        "Static bike wax tracker UI plus agent coaching JSON at GET /agent.json "
        "(browser-friendly) and live Garmin fetch at GET /api/coach."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def write_static_snapshots(snap: dict[str, Any]) -> None:
    """Write GitHub Pages artifacts for agents + UI fallback."""
    text = json.dumps(snap, indent=2, default=str) + "\n"
    AGENT_JSON_PATH.write_text(text, encoding="utf-8")
    AGENT_MD_PATH.write_text(to_agent_markdown(snap), encoding="utf-8")
    COACH_JSON_PATH.write_text(text, encoding="utf-8")


def load_agent_snapshot() -> dict[str, Any]:
    path = AGENT_JSON_PATH if AGENT_JSON_PATH.is_file() else COACH_JSON_PATH
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="No agent snapshot yet. Run the refresh workflow or GET /api/coach.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agent")
@app.get("/agent/")
def agent_page(request: Request) -> Response:
    """Browser: HTML viewer. Agents/API clients: raw JSON (Accept: application/json)."""
    accept = (request.headers.get("accept") or "").lower()
    wants_html = "text/html" in accept and "application/json" not in accept.split(",")[0]
    if wants_html and AGENT_HTML_PATH.is_file():
        return FileResponse(AGENT_HTML_PATH, media_type="text/html")
    return JSONResponse(content=load_agent_snapshot())


@app.get("/agent.json")
def agent_json() -> JSONResponse:
    """Raw coaching JSON with application/json (displays inline in browsers)."""
    return JSONResponse(content=load_agent_snapshot())


@app.get("/agent.md")
def agent_markdown() -> Response:
    """Plain-text Markdown companion for AI retrieval systems."""
    if AGENT_MD_PATH.is_file():
        return FileResponse(AGENT_MD_PATH, media_type="text/markdown; charset=utf-8")
    snap = load_agent_snapshot()
    return Response(content=to_agent_markdown(snap), media_type="text/markdown; charset=utf-8")


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
        try:
            write_static_snapshots(snap)
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
    "agent.json",
    "agent.md",
    "package.json",
    "README.md",
}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/{name}")
def static_file(name: str) -> Response:
    if name == "agent":
        # Handled by /agent routes above; keep as safety net.
        return JSONResponse(content=load_agent_snapshot())
    if name not in STATIC_FILES or not (ROOT / name).is_file():
        raise HTTPException(status_code=404, detail="Not found")
    media = "application/json" if name.endswith(".json") else None
    return FileResponse(ROOT / name, media_type=media)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
