from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.database import init_db

STATIC_DIR = Path(__file__).resolve().parent / "static"


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


def _load_index_html() -> str:
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>YAXIN AI</h1>"


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app/", response_class=HTMLResponse, include_in_schema=False)
async def web_app():
    return HTMLResponse(content=_load_index_html())


@app.get("/static/styles.css", include_in_schema=False)
async def serve_css():
    css_path = STATIC_DIR / "styles.css"
    return Response(
        content=css_path.read_text(encoding="utf-8") if css_path.exists() else "",
        media_type="text/css; charset=utf-8",
    )


@app.get("/static/app.js", include_in_schema=False)
async def serve_js():
    js_path = STATIC_DIR / "app.js"
    return Response(
        content=js_path.read_text(encoding="utf-8") if js_path.exists() else "",
        media_type="application/javascript; charset=utf-8",
    )


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and (STATIC_DIR / "index.html").exists():
        return HTMLResponse(content=_load_index_html())
    return JSONResponse({"message": "Welcome to YAXIN AI", "app_url": "/app"})


@app.get("/health")
async def health():
    return {"status": "healthy"}
