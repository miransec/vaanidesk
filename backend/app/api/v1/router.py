from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, knowledge, voice

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(voice.router)
