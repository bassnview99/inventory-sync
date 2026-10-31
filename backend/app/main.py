from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="Inventory Sync API",
    version="0.1.0",
    description="Middleware de inventario Tiendanube + Mercado Libre. Etapa 1: arquitectura.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "inventory-sync-api", "stage": 1}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Inventory Sync API", "docs": "/docs"}
