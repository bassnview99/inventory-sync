import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON,
    String, Text, UniqueConstraint, Uuid
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    TIENDANUBE = "tiendanube"
    MERCADOLIBRE = "mercadolibre"


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    connections: Mapped[list["PlatformConnection"]] = relationship(back_populates="store")
    products: Mapped[list["Product"]] = relationship(back_populates="store")


class PlatformConnection(Base):
    __tablename__ = "platform_connections"
    __table_args__ = (UniqueConstraint("store_id", "platform", name="uq_connection_store_platform"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(160))
    credentials_encrypted: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="disconnected", nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    store: Mapped["Store"] = relationship(back_populates="connections")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_store_name", "store_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    store: Mapped["Store"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        Index("ix_variants_store_sku", "store_id", "sku"),
        CheckConstraint("length(sku) <= 160", name="ck_variant_sku_length"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(160))
    name: Mapped[str | None] = mapped_column(String(240))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    product: Mapped["Product"] = relationship(back_populates="variants")
    mappings: Mapped[list["ProductMapping"]] = relationship(back_populates="variant", cascade="all, delete-orphan")
    inventory_levels: Mapped[list["InventoryLevel"]] = relationship(back_populates="variant")


class ProductMapping(Base):
    __tablename__ = "product_mappings"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", "external_variant_id", name="uq_mapping_external_variant"),
        Index("ix_mapping_variant_platform", "variant_id", "platform"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_variant_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_sku: Mapped[str | None] = mapped_column(String(160))
    mapping_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    variant: Mapped["ProductVariant"] = relationship(back_populates="mappings")


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"
    __table_args__ = (
        UniqueConstraint("variant_id", "platform", "external_location_id", name="uq_inventory_variant_platform_location"),
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_location_id: Mapped[str] = mapped_column(String(160), default="default", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    variant: Mapped["ProductVariant"] = relationship(back_populates="inventory_levels")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_movements_variant_created", "variant_id", "created_at"),
        CheckConstraint("quantity_before >= 0", name="ck_movement_before_nonnegative"),
        CheckConstraint("quantity_after >= 0", name="ck_movement_after_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(200))
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("webhook_events.id", ondelete="SET NULL"))
    operation_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("store_id", "platform", "external_event_id", name="uq_webhook_external_event"),
        Index("ix_webhook_status_received", "status", "received_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index("ix_sync_jobs_status_next_retry", "status", "next_retry_at"),
        CheckConstraint("attempts >= 0", name="ck_sync_job_attempts_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_variants.id", ondelete="SET NULL"))
    source_platform: Mapped[str | None] = mapped_column(String(30))
    target_platform: Mapped[str | None] = mapped_column(String(30))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(160))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
