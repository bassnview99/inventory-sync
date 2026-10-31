"""Initial schema for single-store inventory sync.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stores",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "platform_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_account_id", sa.String(160)),
        sa.Column("credentials_encrypted", sa.Text()),
        sa.Column("scopes", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("store_id", "platform", name="uq_connection_store_platform"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_store_name", "products", ["store_id", "name"])
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(160)),
        sa.Column("name", sa.String(240)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(sku) <= 160", name="ck_variant_sku_length"),
    )
    op.create_index("ix_variants_store_sku", "product_variants", ["store_id", "sku"])
    op.create_table(
        "product_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_product_id", sa.String(160), nullable=False),
        sa.Column("external_variant_id", sa.String(160), nullable=False),
        sa.Column("external_sku", sa.String(160)),
        sa.Column("mapping_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("store_id", "platform", "external_variant_id", name="uq_mapping_external_variant"),
    )
    op.create_index("ix_mapping_variant_platform", "product_mappings", ["variant_id", "platform"])
    op.create_table(
        "inventory_levels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_location_id", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_sync", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("variant_id", "platform", "external_location_id", name="uq_inventory_variant_platform_location"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_event_id", sa.String(200)),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_fingerprint", sa.String(64)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("store_id", "platform", "external_event_id", name="uq_webhook_external_event"),
    )
    op.create_index("ix_webhook_status_received", "webhook_events", ["status", "received_at"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("movement_type", sa.String(40), nullable=False),
        sa.Column("quantity_before", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("external_reference", sa.String(200)),
        sa.Column("source_event_id", sa.Uuid(), sa.ForeignKey("webhook_events.id", ondelete="SET NULL")),
        sa.Column("operation_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_before >= 0", name="ck_movement_before_nonnegative"),
        sa.CheckConstraint("quantity_after >= 0", name="ck_movement_after_nonnegative"),
    )
    op.create_index("ix_movements_variant_created", "inventory_movements", ["variant_id", "created_at"])
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("product_variants.id", ondelete="SET NULL")),
        sa.Column("source_platform", sa.String(30)),
        sa.Column("target_platform", sa.String(30)),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint("attempts >= 0", name="ck_sync_job_attempts_nonnegative"),
    )
    op.create_index("ix_sync_jobs_status_next_retry", "sync_jobs", ["status", "next_retry_at"])
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(160)),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(160)),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for table in [
        "audit_logs", "sync_logs", "sync_jobs", "inventory_movements",
        "webhook_events", "inventory_levels", "product_mappings",
        "product_variants", "products", "platform_connections", "stores"
    ]:
        op.drop_table(table)
