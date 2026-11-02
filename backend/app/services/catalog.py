"""Importación de catálogo de solo lectura: nunca escribe en la plataforma externa."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.tiendanube import TiendanubeClient, TiendanubeError
from app.integrations.tiendanube.normalize import NormalizedVariant, normalize_product
from app.models import ExternalVariant, Platform, SyncJob, SyncLog, utcnow
from app.services import connections


async def _upsert(db: AsyncSession, store_id: uuid.UUID, platform: str, rows: list[NormalizedVariant]) -> dict:
    existing = {
        v.external_variant_id: v
        for v in (await db.execute(
            select(ExternalVariant).where(ExternalVariant.store_id == store_id, ExternalVariant.platform == platform)
        )).scalars()
    }
    now = utcnow()
    created = updated = 0
    for row in rows:
        current = existing.get(row.external_variant_id)
        if current is None:
            db.add(ExternalVariant(store_id=store_id, platform=platform, synced_at=now, **row.__dict__))
            created += 1
            continue
        for field, value in row.__dict__.items():
            setattr(current, field, value)
        current.active = True
        current.synced_at = now
        updated += 1
    seen = {r.external_variant_id for r in rows}
    gone = [v for k, v in existing.items() if k not in seen and v.active]
    for v in gone:
        v.active = False  # solo tras una lectura completa y exitosa
    return {"created": created, "updated": updated, "deactivated": len(gone), "total": len(rows)}


async def import_tiendanube_catalog(db: AsyncSession, store_id: uuid.UUID, *, transport=None, sleep=None) -> SyncJob:
    job = SyncJob(store_id=store_id, source_platform=Platform.TIENDANUBE.value, job_type="catalog_import",
                  status="running", attempts=1, idempotency_key=f"catalog_import:{uuid.uuid4()}")
    db.add(job)
    await db.commit()
    job_id = job.id  # se guarda: tras un rollback el objeto expira

    async def log(level: str, message: str, details: dict | None = None):
        db.add(SyncLog(job_id=job_id, level=level, message=message, details=details))

    conn = await connections.get_connection(db, store_id, Platform.TIENDANUBE.value)
    try:
        creds = connections.read_credentials(conn)
        if creds is None:
            raise TiendanubeError("Tiendanube no está conectada.")
        kwargs = {"transport": transport}
        if sleep:
            kwargs["sleep"] = sleep
        rows: list[NormalizedVariant] = []
        async with TiendanubeClient(creds["user_id"], creds["access_token"], **kwargs) as client:
            async for product in client.iter_products():
                rows.extend(normalize_product(product))
        summary = await _upsert(db, store_id, Platform.TIENDANUBE.value, rows)
        job.status = "completed"
        await log("info", "Catálogo de Tiendanube importado.", summary)
    except TiendanubeError as exc:
        await db.rollback()
        job = await db.get(SyncJob, job_id)
        job.status = "failed"
        job.error_message = str(exc)
        if exc.status_code in (401, 403) and conn is not None:
            conn = await connections.get_connection(db, store_id, Platform.TIENDANUBE.value)
            conn.status = "error"
        await log("error", str(exc), {"status_code": exc.status_code, "retryable": exc.retryable})
    except ValueError as exc:  # credenciales no descifrables
        await db.rollback()
        job = await db.get(SyncJob, job_id)
        job.status = "failed"
        job.error_message = str(exc)
        await log("error", str(exc))
    job.completed_at = utcnow()
    await db.commit()
    return job


async def tiendanube_stats(db: AsyncSession, store_id: uuid.UUID) -> dict:
    rows = (await db.execute(
        select(ExternalVariant).where(ExternalVariant.store_id == store_id,
                                      ExternalVariant.platform == Platform.TIENDANUBE.value,
                                      ExternalVariant.active.is_(True))
    )).scalars().all()
    return {
        "variants": len(rows),
        "without_sku": sum(1 for r in rows if not r.sku),
        "unmanaged_stock": sum(1 for r in rows if r.stock is None),
        "last_synced_at": max((r.synced_at for r in rows), default=None),
    }
