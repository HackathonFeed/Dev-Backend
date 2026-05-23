from fastapi import APIRouter

from app.api.routes import admin, ai, auth, bookmarks, hackathons, platforms, themes, trends, users

api_router = APIRouter()
api_router.include_router(ai.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(hackathons.router)
api_router.include_router(bookmarks.router)
api_router.include_router(themes.router)
api_router.include_router(platforms.router)
api_router.include_router(trends.router)
api_router.include_router(admin.router)
