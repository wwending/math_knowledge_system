from fastapi import APIRouter

from app.api.v1 import admin_users, auth, endpoints, feedback


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(feedback.router)
api_router.include_router(feedback.admin_router)
api_router.include_router(endpoints.router)
