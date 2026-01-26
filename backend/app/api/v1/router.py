from fastapi import APIRouter

from app.api.v1 import auth, endpoints

api_router = APIRouter()
api_router.include_router(auth.router)       # /auth/...
api_router.include_router(endpoints.router)  # 你的业务接口
