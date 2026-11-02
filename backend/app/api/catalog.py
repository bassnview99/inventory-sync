from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.connections import get_transport
from app.database import get_db
from app.models import ExternalVariant, Platform, SyncJob, SyncLog
from app.security import require_admin
from app.services import catalog, connections

router = APIRouter(prefix="/api", tags=["catalog"], dependencies=[Depends(require_admin)])


def _job_view(job: SyncJob, logs: list[SyncLog] | None = None) -> dict:
    return {
        "id": str(job.id), "job_type": job.job_type, "status": job.status,
        "source_platform": job.source_platform, "error_message": job.error_message,
        "created_at": job.created_at, "completed_at": job.completed_at,
        "logs": [{"level": l.level, "message": l.message, "details": l.details, "created_at": l.created_at}
                 for l in (logs or [])],
    }


@router.post("/catalog/tiendanube/import")
async def import_tiendanube(db: AsyncSession = Depends(get_db), transport=Depends(get_transport)):
    """Lee el catálogo completo de Tiendanube y lo guarda localmente. No modifica nada en Tiendanube."""
    store = await connections.get_or_create_store(db)
    job = await catalog.import_tiendanube_catalog(db, store.id, transport=transport)
    logs = (await db.execute(select(SyncLog).where(SyncLog.job_id == job.id).order_by(SyncLog.created_at))).scalars().all()
    return _job_view(job, list(logs))


@router.get("/catalog/variants")
async def list_variants(platform: str = Query(Platform.TIENDANUBE.value), q: str | None = None,
                        only_without_sku: bool = False, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    cond = [ExternalVariant.store_id == store.id, ExternalVariant.platform == platform, ExternalVariant.active.is_(True)]
    if q:
        like = f"%{q.strip()}%"
        cond.append(or_(ExternalVariant.sku.ilike(like), ExternalVariant.product_name.ilike(like),
                        ExternalVariant.variant_name.ilike(like)))
    if only_without_sku:
        cond.append(ExternalVariant.sku.is_(None))
    total = (await db.execute(select(func.count()).select_from(ExternalVariant).where(*cond))).scalar_one()
    rows = (await db.execute(
        select(ExternalVariant).where(*cond).order_by(ExternalVariant.product_name, ExternalVariant.variant_name)
        .limit(limit).offset(offset)
    )).scalars().all()
    return {
        "total": total,
        "items": [{
            "id": str(r.id), "platform": r.platform, "product_id": r.external_product_id,
            "variant_id": r.external_variant_id, "product_name": r.product_name, "variant_name": r.variant_name,
            "sku": r.sku, "stock": r.stock, "inventory_levels": r.inventory_levels,
            "published": r.published, "synced_at": r.synced_at,
        } for r in rows],
    }


@router.get("/catalog/tiendanube/stats")
async def tiendanube_stats(db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    return await catalog.tiendanube_stats(db, store.id)


@router.get("/sync/jobs")
async def list_jobs(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    store = await connections.get_or_create_store(db)
    jobs = (await db.execute(
        select(SyncJob).where(SyncJob.store_id == store.id).order_by(SyncJob.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"items": [_job_view(j) for j in jobs]}
