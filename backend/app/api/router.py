from fastapi import APIRouter
from app.api.v1 import assistant, reminders, security, users, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(assistant.router, tags=["Assistant"])
api_router.include_router(reminders.router, tags=["Reminders"])
api_router.include_router(security.router, tags=["Security"])
api_router.include_router(users.router, tags=["Users"])

