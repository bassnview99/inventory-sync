from fastapi import APIRouter

from app.api import catalog, connections

api_router = APIRouter()
api_router.include_router(connections.router)
api_router.include_router(catalog.router)
