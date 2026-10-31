from app.models import Base


def test_expected_tables_exist():
    expected = {
        "stores", "platform_connections", "products", "product_variants",
        "product_mappings", "inventory_levels", "inventory_movements",
        "webhook_events", "sync_jobs", "sync_logs", "audit_logs",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_sync_job_has_unique_idempotency_key():
    table = Base.metadata.tables["sync_jobs"]
    constraints = [c for c in table.constraints if getattr(c, "name", None) == "uq_sync_jobs_idempotency_key"]
    # SQLAlchemy unique=True creates a unique constraint/index; assert the column itself is unique.
    assert table.c.idempotency_key.unique is True
