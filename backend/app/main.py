from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings

app = FastAPI(
    title="Inventory Sync API",
    version="0.2.0",
    description="Middleware de inventario Tiendanube + Mercado Libre. Etapa 2: conexión y catálogo de Tiendanube (solo lectura).",
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
         "https://spindly-spooky-spider-wwxx7gj7w95h9pgj-5173.app.github.dev",
        settings.frontend_url.rstrip("/"),
    ],
    allow_origin_regex=r"^https://[a-z0-9-]+-5173\.app\.github\.dev$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
      allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "inventory-sync-api", "stage": 2}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Inventory Sync API", "docs": "/docs"}
