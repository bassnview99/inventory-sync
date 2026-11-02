from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings

app = FastAPI(
    title="Inventory Sync API",
    version="0.2.0",
    description="Middleware de inventario Tiendanube + Mercado Libre. Etapa 2: conexión y catálogo de Tiendanube (solo lectura).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Admin-Key"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "inventory-sync-api", "stage": 2}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Inventory Sync API", "docs": "/docs"}
