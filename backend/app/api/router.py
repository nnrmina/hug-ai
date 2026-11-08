from fastapi import APIRouter, Depends
from app.api.v1 import assistant, auth, reminders, security, users, health
from app.core.auth import require_api_key

api_router = APIRouter()

# Health stays public so uptime checks work without credentials.
api_router.include_router(health.router, tags=["Health"])

_api_key = [Depends(require_api_key)]
# Device registration issues tokens; every other router authenticates with that token.
api_router.include_router(auth.router, tags=["Auth"], dependencies=_api_key)
api_router.include_router(assistant.router, tags=["Assistant"], dependencies=_api_key)
api_router.include_router(reminders.router, tags=["Reminders"], dependencies=_api_key)
api_router.include_router(security.router, tags=["Security"], dependencies=_api_key)
api_router.include_router(users.router, tags=["Users"], dependencies=_api_key)
