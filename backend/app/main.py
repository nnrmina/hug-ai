import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.database import init_db

# Single source of truth for the web app: <repo>/public (also served as-is by Vercel).
REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR") or REPO_ROOT / "public").resolve()

# Windows' registry often maps .js to text/plain, which breaks ES modules.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")

# Top-level files the PWA needs at the site root (same paths Vercel serves from public/)
ROOT_FILES = {
    "sw.js": {"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    "manifest.webmanifest": {"Cache-Control": "no-cache"},
    "favicon.svg": {},
    "favicon.ico": {},
    "robots.txt": {},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="YAXIN AI API",
    description="Voice-powered AI Digital Assistant & Digital Life Agent (Azerbaijan MVP)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

for _sub in ("static", "icons"):
    # check_dir=False: folders created after startup (or missing in a slim build) still work
    app.mount(f"/{_sub}", StaticFiles(directory=str(PUBLIC_DIR / _sub), check_dir=False), name=_sub)


@app.get("/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
async def web_app():
    index_path = PUBLIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="public/index.html not found")
    return FileResponse(index_path, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
async def health():
    # GIT_SHA is injected at deploy time (deploy/deploy.sh) so you can see what is live
    return {"status": "healthy", "version": os.environ.get("GIT_SHA", "dev")}


@app.get("/{filename}", include_in_schema=False)
async def root_file(filename: str):
    headers = ROOT_FILES.get(filename)
    path = PUBLIC_DIR / filename
    if headers is None or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, headers=headers)
