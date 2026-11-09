import asyncio
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
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
    "family.html": {"Cache-Control": "no-cache"},
    "favicon.ico": {},
    "robots.txt": {},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop = asyncio.Event()
    task = None
    if settings.SCHEDULER_ENABLED:
        from app.services.scheduler import scheduler_loop

        task = asyncio.create_task(scheduler_loop(stop))
    yield
    stop.set()
    if task:
        await asyncio.wait([task], timeout=5)


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



@app.middleware("http")
async def static_cache_headers(request, call_next):
    """Code (CSS/JS) must always be revalidated, or a deploy shows new HTML with old styles.
    ETags keep that cheap (304). Media rarely changes and can be cached for a week."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path.startswith("/icons/"):
        if path.startswith("/icons/") or path.endswith((".css", ".js", ".html", ".json")):
            response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers.setdefault("Cache-Control", "public, max-age=604800")
    return response


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
    # Version the entry files so a new deploy can never pair new HTML with old CSS/JS
    version = os.environ.get("GIT_SHA", "dev")
    html = index_path.read_text(encoding="utf-8")
    html = html.replace('href="/static/styles.css"', f'href="/static/styles.css?v={version}"')
    html = html.replace('src="/static/js/main.js"', f'src="/static/js/main.js?v={version}"')
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/f/{token}", include_in_schema=False)
async def family_page(token: str):
    """Private family view (the token in the URL is the credential; the page calls /api/v1/family/{token})."""
    page = PUBLIC_DIR / "family.html"
    if not page.exists():
        raise HTTPException(status_code=404)
    return FileResponse(page, media_type="text/html", headers={"Cache-Control": "no-cache", "Referrer-Policy": "no-referrer"})


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
    if filename == "sw.js":
        # Stamp the deployed commit into the service worker's cache name: every deploy
        # becomes a new SW version, so installed phones drop the old cached app shell.
        source = path.read_text(encoding="utf-8")
        version = os.environ.get("GIT_SHA", "dev")
        source = re.sub(r'const VERSION = "([^"]*)";', lambda m: f'const VERSION = "{m.group(1)}-{version}";', source, count=1)
        return Response(source, media_type="application/javascript", headers=headers)
    return FileResponse(path, headers=headers)
