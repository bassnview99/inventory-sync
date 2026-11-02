import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, OAuthState, Platform, PlatformConnection, Store, utcnow
from app.security import decrypt_credentials, encrypt_credentials, new_state

STATE_TTL = timedelta(minutes=10)


async def get_or_create_store(db: AsyncSession) -> Store:
    """Despliegue de una sola tienda: se crea una tienda por defecto en el primer uso."""
    store = (await db.execute(select(Store).order_by(Store.created_at).limit(1))).scalar_one_or_none()
    if store is None:
        store = Store(name="Mi tienda")
        db.add(store)
        await db.commit()
    return store


async def get_connection(db: AsyncSession, store_id: uuid.UUID, platform: str) -> PlatformConnection | None:
    return (await db.execute(
        select(PlatformConnection).where(PlatformConnection.store_id == store_id, PlatformConnection.platform == platform)
    )).scalar_one_or_none()


async def create_oauth_state(db: AsyncSession, store_id: uuid.UUID, platform: str) -> str:
    now = utcnow()
    await db.execute(delete(OAuthState).where(OAuthState.expires_at < now))  # limpieza oportunista
    state = new_state()
    db.add(OAuthState(state=state, store_id=store_id, platform=platform, expires_at=now + STATE_TTL))
    await db.commit()
    return state


async def consume_oauth_state(db: AsyncSession, state: str, platform: str) -> uuid.UUID | None:
    """Devuelve el store_id si el state existe, es de la plataforma y no caducó. Siempre lo invalida."""
    row = await db.get(OAuthState, state)
    if row is None:
        return None
    await db.delete(row)
    await db.commit()
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if row.platform != platform or expires < utcnow():
        return None
    return row.store_id


async def save_credentials(db: AsyncSession, store_id: uuid.UUID, platform: str, *, account_id: str,
                           credentials: dict, scopes: str | None) -> PlatformConnection:
    conn = await get_connection(db, store_id, platform)
    if conn is None:
        conn = PlatformConnection(store_id=store_id, platform=platform)
        db.add(conn)
    conn.external_account_id = account_id
    conn.credentials_encrypted = encrypt_credentials(credentials)
    conn.scopes = scopes
    conn.status = "connected"
    conn.connected_at = utcnow()
    db.add(AuditLog(store_id=store_id, actor_type="admin", action="connection.connected",
                    entity_type="platform_connection", entity_id=platform, details={"account_id": account_id, "scopes": scopes}))
    await db.commit()
    return conn


async def disconnect(db: AsyncSession, store_id: uuid.UUID, platform: str) -> bool:
    conn = await get_connection(db, store_id, platform)
    if conn is None:
        return False
    conn.credentials_encrypted = None
    conn.status = "disconnected"
    db.add(AuditLog(store_id=store_id, actor_type="admin", action="connection.disconnected",
                    entity_type="platform_connection", entity_id=platform))
    await db.commit()
    return True


def read_credentials(conn: PlatformConnection | None) -> dict | None:
    if conn is None or conn.status != "connected" or not conn.credentials_encrypted:
        return None
    return decrypt_credentials(conn.credentials_encrypted)


async def mark_connection_error(db: AsyncSession, conn: PlatformConnection, status: str = "error") -> None:
    conn.status = status
    await db.commit()


def public_view(platform: str, conn: PlatformConnection | None) -> dict:
    return {
        "platform": platform,
        "status": conn.status if conn else "disconnected",
        "account_id": conn.external_account_id if conn else None,
        "scopes": conn.scopes if conn else None,
        "connected_at": conn.connected_at if conn else None,
    }


ALL_PLATFORMS = [Platform.TIENDANUBE.value, Platform.MERCADOLIBRE.value]
