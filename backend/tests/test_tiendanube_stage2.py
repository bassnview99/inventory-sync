import httpx
import pytest
from sqlalchemy import select

from app.integrations.tiendanube import TiendanubeClient, TiendanubeError
from app.integrations.tiendanube.normalize import normalize_product
from app.models import AuditLog, ExternalVariant, PlatformConnection
from app.security import decrypt_credentials, encrypt_credentials
from app.main import app
from tests.conftest import ADMIN, make_product


# ---------- cifrado ----------

def test_credentials_roundtrip_and_not_plaintext(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "token_encryption_key", "a-test-encryption-secret-of-32-chars!!")
    blob = encrypt_credentials({"access_token": "abc"})
    assert "abc" not in blob
    assert decrypt_credentials(blob) == {"access_token": "abc"}


def test_production_rejects_placeholder_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "token_encryption_key", "development-only-change-me")
    with pytest.raises(RuntimeError):
        encrypt_credentials({"a": 1})


# ---------- normalización ----------

def test_normalize_handles_names_sku_and_stock():
    rows = normalize_product({
        "id": 1, "name": {"es": "Remera", "pt": "Camiseta"}, "published": False,
        "variants": [
            {"id": 10, "sku": " R-ROJA-M ", "stock": 5, "values": [{"es": "Rojo"}, {"es": "M"}]},
            {"id": 11, "sku": "", "stock": None, "values": []},
            {"id": 12, "sku": "X", "stock": 99, "inventory_levels": [
                {"location_id": "a", "stock": 2}, {"location_id": "b", "stock": 3}]},
        ],
    })
    assert [r.external_variant_id for r in rows] == ["10", "11", "12"]
    assert rows[0].sku == "R-ROJA-M" and rows[0].variant_name == "Rojo / M" and rows[0].stock == 5
    assert rows[0].published is False
    assert rows[1].sku is None and rows[1].stock is None and rows[1].variant_name is None
    assert rows[2].stock == 5 and len(rows[2].inventory_levels) == 2


# ---------- cliente ----------

async def test_client_follows_link_pagination_and_sends_headers():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2}])
        return httpx.Response(200, json=[{"id": 1}], headers={
            "Link": '<https://api.tiendanube.com/v1/9/products?page=2&per_page=200>; rel="next"'})

    async with TiendanubeClient("9", "tok", transport=httpx.MockTransport(handler)) as c:
        ids = [p["id"] async for p in c.iter_products()]
    assert ids == [1, 2]
    assert seen[0].headers["User-Agent"]
    assert seen[0].headers["Authentication"] == "bearer tok"
    assert seen[0].url.params["per_page"] == "200"


async def test_client_retries_429_using_rate_limit_reset():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"X-Rate-Limit-Reset": "1500"})
        return httpx.Response(200, json=[])

    async def fake_sleep(s):
        sleeps.append(s)

    async with TiendanubeClient("9", "tok", transport=httpx.MockTransport(handler), sleep=fake_sleep) as c:
        assert [p async for p in c.iter_products()] == []
    assert len(calls) == 2 and 1.5 <= sleeps[0] < 2.0


async def test_client_gives_up_after_max_retries():
    async def fake_sleep(s):
        pass

    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    async with TiendanubeClient("9", "tok", transport=transport, sleep=fake_sleep) as c:
        with pytest.raises(TiendanubeError) as err:
            [p async for p in c.iter_products()]
    assert err.value.retryable


async def test_client_empty_store_404_is_empty_and_401_is_error():
    async with TiendanubeClient("9", "t", transport=httpx.MockTransport(lambda r: httpx.Response(404))) as c:
        assert [p async for p in c.iter_products()] == []
    async with TiendanubeClient("9", "t", transport=httpx.MockTransport(lambda r: httpx.Response(401))) as c:
        with pytest.raises(TiendanubeError) as err:
            [p async for p in c.iter_products()]
    assert err.value.status_code == 401


# ---------- API: autenticación del panel ----------

async def test_api_requires_admin_key(client):
    assert (await client.get("/api/connections")).status_code == 401
    assert (await client.get("/api/connections", headers={"X-Admin-Key": "nope"})).status_code == 401
    assert (await client.get("/api/connections", headers=ADMIN)).status_code == 200


async def test_api_disabled_without_configured_key(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "")
    assert (await client.get("/api/connections", headers=ADMIN)).status_code == 503


# ---------- API: OAuth ----------

async def _authorize(client) -> str:
    resp = await client.post("/api/connections/tiendanube/authorize", headers=ADMIN)
    assert resp.status_code == 200
    url = resp.json()["authorize_url"]
    assert url.startswith("https://www.tiendanube.com/apps/app123/authorize?state=")
    return url.split("state=")[1]


async def _connect(client) -> None:
    state = await _authorize(client)
    resp = await client.get("/api/connections/tiendanube/callback", params={"code": "abc", "state": state})
    assert resp.status_code == 303 and resp.headers["location"].endswith("tiendanube=connected")


async def test_oauth_flow_stores_encrypted_token(client, fake_tn):
    await _connect(client)
    status = (await client.get("/api/connections", headers=ADMIN)).json()
    tn = next(c for c in status["connections"] if c["platform"] == "tiendanube")
    assert tn["status"] == "connected" and tn["account_id"] == "777" and tn["scopes"] == "read_products"
    assert "tok_secret_123" not in (await client.get("/api/connections", headers=ADMIN)).text  # nunca se expone

    async with app.state.session_maker() as db:
        conn = (await db.execute(select(PlatformConnection))).scalar_one()
        assert "tok_secret_123" not in conn.credentials_encrypted
        assert decrypt_credentials(conn.credentials_encrypted)["access_token"] == "tok_secret_123"
        assert (await db.execute(select(AuditLog).where(AuditLog.action == "connection.connected"))).scalar_one()
    token_req = next(r for r in fake_tn.requests if r.url.path == "/apps/authorize/token")
    assert b'"grant_type":"authorization_code"' in token_req.content.replace(b" ", b"")


async def test_callback_rejects_unknown_and_reused_state(client):
    r = await client.get("/api/connections/tiendanube/callback", params={"code": "abc", "state": "forged"})
    assert r.headers["location"].endswith("tiendanube=error_invalid_state")
    state = await _authorize(client)
    ok = await client.get("/api/connections/tiendanube/callback", params={"code": "abc", "state": state})
    assert ok.headers["location"].endswith("tiendanube=connected")
    again = await client.get("/api/connections/tiendanube/callback", params={"code": "abc", "state": state})
    assert again.headers["location"].endswith("tiendanube=error_invalid_state")  # un solo uso


async def test_callback_missing_params_and_token_failure(client, fake_tn):
    r = await client.get("/api/connections/tiendanube/callback")
    assert r.headers["location"].endswith("tiendanube=error_missing_params")
    fake_tn.token_status = 400
    state = await _authorize(client)
    r = await client.get("/api/connections/tiendanube/callback", params={"code": "expired", "state": state})
    assert r.headers["location"].endswith("tiendanube=error_token_exchange")
    tn = next(c for c in (await client.get("/api/connections", headers=ADMIN)).json()["connections"]
              if c["platform"] == "tiendanube")
    assert tn["status"] == "disconnected"


async def test_authorize_without_app_id_is_503(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "tiendanube_app_id", "")
    assert (await client.post("/api/connections/tiendanube/authorize", headers=ADMIN)).status_code == 503


async def test_disconnect_clears_credentials(client):
    await _connect(client)
    assert (await client.delete("/api/connections/tiendanube", headers=ADMIN)).status_code == 200
    async with app.state.session_maker() as db:
        conn = (await db.execute(select(PlatformConnection))).scalar_one()
        assert conn.credentials_encrypted is None and conn.status == "disconnected"


# ---------- API: importación de catálogo ----------

async def test_import_requires_connection(client):
    job = (await client.post("/api/catalog/tiendanube/import", headers=ADMIN)).json()
    assert job["status"] == "failed" and "no está conectada" in job["error_message"]


async def test_import_upserts_paginates_and_deactivates_missing(client, fake_tn):
    await _connect(client)
    fake_tn.products_pages = [
        [make_product(1, "Remera", [{"id": 10, "sku": "R-1", "stock": 4, "values": [{"es": "Rojo"}]},
                                    {"id": 11, "sku": None, "stock": None, "values": [{"es": "Azul"}]}])],
        [make_product(2, "Gorra", [{"id": 20, "sku": "G-1", "stock": 0, "values": []}])],
    ]
    job = (await client.post("/api/catalog/tiendanube/import", headers=ADMIN)).json()
    assert job["status"] == "completed"
    assert job["logs"][0]["details"] == {"created": 3, "updated": 0, "deactivated": 0, "total": 3}

    data = (await client.get("/api/catalog/variants", headers=ADMIN)).json()
    assert data["total"] == 3
    gorra = next(i for i in data["items"] if i["sku"] == "G-1")
    assert gorra["stock"] == 0  # 0 no es lo mismo que "sin control de stock"

    stats = (await client.get("/api/catalog/tiendanube/stats", headers=ADMIN)).json()
    assert stats["variants"] == 3 and stats["without_sku"] == 1 and stats["unmanaged_stock"] == 1

    # segunda importación: cambia stock, desaparece la variante 20
    fake_tn.products_pages = [[make_product(1, "Remera", [
        {"id": 10, "sku": "R-1", "stock": 9, "values": [{"es": "Rojo"}]},
        {"id": 11, "sku": "R-2", "stock": 1, "values": [{"es": "Azul"}]}])]]
    job2 = (await client.post("/api/catalog/tiendanube/import", headers=ADMIN)).json()
    assert job2["logs"][0]["details"] == {"created": 0, "updated": 2, "deactivated": 1, "total": 2}
    items = (await client.get("/api/catalog/variants", headers=ADMIN)).json()["items"]
    assert {i["sku"]: i["stock"] for i in items} == {"R-1": 9, "R-2": 1}

    jobs = (await client.get("/api/sync/jobs", headers=ADMIN)).json()["items"]
    assert [j["status"] for j in jobs] == ["completed", "completed"]


async def test_import_is_read_only_against_tiendanube(client, fake_tn):
    await _connect(client)
    fake_tn.products_pages = [[make_product(1, "A", [{"id": 1, "sku": "A", "stock": 1}])]]
    await client.post("/api/catalog/tiendanube/import", headers=ADMIN)
    api_calls = [r for r in fake_tn.requests if r.url.path.endswith("/products")]
    assert api_calls and all(r.method == "GET" for r in api_calls)


async def test_failed_import_keeps_previous_catalog_and_flags_connection(client, fake_tn):
    await _connect(client)
    fake_tn.products_pages = [[make_product(1, "A", [{"id": 1, "sku": "A", "stock": 1}])]]
    await client.post("/api/catalog/tiendanube/import", headers=ADMIN)

    original = fake_tn.handler
    fake_tn.handler = lambda req: httpx.Response(401) if req.url.path.endswith("/products") else original(req)
    from app.api.connections import get_transport
    app.dependency_overrides[get_transport] = lambda: httpx.MockTransport(fake_tn.handler)

    job = (await client.post("/api/catalog/tiendanube/import", headers=ADMIN)).json()
    assert job["status"] == "failed" and "token" in job["error_message"]
    assert (await client.get("/api/catalog/variants", headers=ADMIN)).json()["total"] == 1  # no se borró nada
    tn = next(c for c in (await client.get("/api/connections", headers=ADMIN)).json()["connections"]
              if c["platform"] == "tiendanube")
    assert tn["status"] == "error"


async def test_variant_search_and_filters(client, fake_tn):
    await _connect(client)
    fake_tn.products_pages = [[
        make_product(1, "Remera Lisa", [{"id": 1, "sku": "REM-1", "stock": 1}, {"id": 2, "sku": None, "stock": 1}]),
        make_product(2, "Gorra", [{"id": 3, "sku": "GOR-1", "stock": 1}]),
    ]]
    await client.post("/api/catalog/tiendanube/import", headers=ADMIN)
    by_sku = (await client.get("/api/catalog/variants", params={"q": "gor"}, headers=ADMIN)).json()
    assert by_sku["total"] == 1 and by_sku["items"][0]["sku"] == "GOR-1"
    nosku = (await client.get("/api/catalog/variants", params={"only_without_sku": "true"}, headers=ADMIN)).json()
    assert nosku["total"] == 1 and nosku["items"][0]["product_name"] == "Remera Lisa"
    page = (await client.get("/api/catalog/variants", params={"limit": 1, "offset": 1}, headers=ADMIN)).json()
    assert page["total"] == 3 and len(page["items"]) == 1
