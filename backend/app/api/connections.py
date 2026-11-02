from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.integrations.tiendanube import TiendanubeError, build_authorize_url, exchange_code
from app.models import Platform
from app.security import require_admin
from app.services import connections

router = APIRouter(prefix="/api/connections", tags=["connections"])

# Se sobrescribe en pruebas para simular la API de Tiendanube.
def get_transport():
    return None


@router.get("", dependencies=[Depends(require_admin)])
async def list_connections(db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    return {
        "store": {"id": str(store.id), "name": store.name},
        "connections": [
            connections.public_view(p, await connections.get_connection(db, store.id, p))
            for p in connections.ALL_PLATFORMS
        ],
    }


@router.post("/tiendanube/authorize", dependencies=[Depends(require_admin)])
async def tiendanube_authorize(db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    state = await connections.create_oauth_state(db, store.id, Platform.TIENDANUBE.value)
    try:
        return {"authorize_url": build_authorize_url(state)}
    except TiendanubeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/tiendanube/callback", include_in_schema=False)
async def tiendanube_callback(code: str | None = Query(None), state: str | None = Query(None),
                              db: AsyncSession = Depends(get_db), transport=Depends(get_transport)):
    """Destino de la redirección de Tiendanube. Lo abre el navegador, por eso no exige la clave de admin:
    se protege con el `state` de un solo uso generado en /authorize."""
    def back(result: str) -> RedirectResponse:
        return RedirectResponse(f"{settings.frontend_url}/?{urlencode({'tiendanube': result})}", status_code=303)

    if not code or not state:
        return back("error_missing_params")
    store_id = await connections.consume_oauth_state(db, state, Platform.TIENDANUBE.value)
    if store_id is None:
        return back("error_invalid_state")
    try:
        token = await exchange_code(code, transport=transport)
    except TiendanubeError:
        return back("error_token_exchange")
    await connections.save_credentials(
        db, store_id, Platform.TIENDANUBE.value,
        account_id=str(token["user_id"]),
        credentials={"access_token": token["access_token"], "user_id": str(token["user_id"]),
                     "token_type": token.get("token_type", "bearer")},
        scopes=token.get("scope"),
    )
    return back("connected")


@router.delete("/tiendanube", dependencies=[Depends(require_admin)])
async def tiendanube_disconnect(db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    await connections.disconnect(db, store.id, Platform.TIENDANUBE.value)
    return {"status": "disconnected"}
