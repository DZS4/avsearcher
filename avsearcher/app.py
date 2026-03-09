from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .search import SearchService


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
service = SearchService()

app = FastAPI(title="AVSearcher", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/sources")
def sources() -> dict:
    return {"items": service.list_sources()}


@app.get("/api/search")
def search(
    q: str = Query(default=""),
    sources: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    days: int = Query(default=3650, ge=1, le=3650),
    sort: str = Query(default="latest"),
) -> dict:
    return service.search(query=q, selected_sources=sources, limit=limit, days=days, sort=sort)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
