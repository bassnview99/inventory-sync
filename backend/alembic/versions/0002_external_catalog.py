"""Catálogo externo (solo lectura) y estados OAuth.

Revision ID: 0002_external_catalog
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_external_catalog"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(128), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "external_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("external_product_id", sa.String(160), nullable=False),
        sa.Column("external_variant_id", sa.String(160), nullable=False),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column("variant_name", sa.String(240)),
        sa.Column("sku", sa.String(160)),
        sa.Column("stock", sa.Integer()),
        sa.Column("inventory_levels", sa.JSON()),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("store_id", "platform", "external_variant_id", name="uq_external_variant"),
    )
    op.create_index("ix_external_variants_sku", "external_variants", ["store_id", "platform", "sku"])


def downgrade():
    op.drop_index("ix_external_variants_sku", table_name="external_variants")
    op.drop_table("external_variants")
    op.drop_table("oauth_states")
