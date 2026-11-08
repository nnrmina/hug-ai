from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.database import check_db_connection, engine

router = APIRouter()


@router.get("/health")
async def health_check():
    db_ok = check_db_connection()
    body = {
        "status": "healthy" if db_ok else "degraded",
        "database": engine.dialect.name if db_ok else "unreachable",
    }
    return JSONResponse(content=body, status_code=200 if db_ok else 503)
