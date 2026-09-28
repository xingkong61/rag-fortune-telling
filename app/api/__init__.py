"""API 路由。"""
from fastapi import APIRouter

from app.api import chat, fate, info, liuyao, meihua

router = APIRouter(prefix="/api")
router.include_router(fate.router)
router.include_router(meihua.router)
router.include_router(liuyao.router)
router.include_router(chat.router)
router.include_router(info.router)