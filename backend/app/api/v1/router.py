from fastapi import APIRouter

from app.api.v1 import ai, auth, candidates, offers, public, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(candidates.router)
api_router.include_router(search.router)
api_router.include_router(offers.router)
api_router.include_router(ai.router)
api_router.include_router(public.router)
