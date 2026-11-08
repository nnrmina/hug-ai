from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import logger

# Refuse to start with an insecure production configuration (SQLite, missing JWT_SECRET, CORS "*").
settings.validate_for_production()


def _resolve_web_dir() -> Path:
    """Single source of truth for the web UI: the repository's public/ folder.

    Locally: <repo>/public. In Docker the folder is copied to /public (see backend/Dockerfile).
    """
    here = Path(__file__).resolve()
    for candidate in (here.parents[2] / "public", Path("/public")):
        if (candidate / "index.html").exists():
            return candidate
    return here.parents[2] / "public"


WEB_DIR = _resolve_web_dir()
STATIC_DIR = WEB_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Serverless runtimes (Vercel) may not run lifespan events, so tables are ensured at import too.
# create_all only creates missing tables; existing tables and data are never touched.
init_db()


app = FastAPI(
    title="YAXIN AI API",
    description="Voice-powered AI Digital Assistant & Digital Life Agent (Azerbaijan MVP)",
    version="1.0.0",
    lifespan=lifespan,
)

# Credentials (cookies) are never used by this API, so they are not allowed cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the details server-side; never leak stack traces or internals to clients.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Daxili server xətası baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."},
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    return response


app.include_router(api_router, prefix="/api/v1")


def _load_index_html() -> str:
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>YAXIN AI</h1>"


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app/", response_class=HTMLResponse, include_in_schema=False)
async def web_app():
    return HTMLResponse(content=_load_index_html())


@app.get("/health")
async def health():
    return {"status": "healthy"}
