import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.connections import get_transport
from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base

ADMIN = {"X-Admin-Key": "test-admin-key"}


class FakeTiendanube:
    """Simula token endpoint y /products con paginación por cabecera Link."""

    def __init__(self):
        self.products_pages: list[list[dict]] = [[]]
        self.token_status = 200
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/apps/authorize/token":
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "tok_secret_123", "token_type": "bearer",
                                             "scope": "read_products", "user_id": 777})
        if request.url.path.endswith("/products"):
            page = int(request.url.params.get("page", "1"))
            body = self.products_pages[page - 1]
            headers = {}
            if page < len(self.products_pages):
                headers["Link"] = f'<https://api.tiendanube.com/v1/777/products?page={page + 1}&per_page=200>; rel="next"'
            return httpx.Response(200, json=body, headers=headers)
        return httpx.Response(404, json={})


@pytest.fixture
def fake_tn():
    return FakeTiendanube()


@pytest_asyncio.fixture
async def client(monkeypatch, fake_tn):
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-key")
    monkeypatch.setattr(settings, "tiendanube_app_id", "app123")
    monkeypatch.setattr(settings, "tiendanube_client_secret", "shh")
    monkeypatch.setattr(settings, "token_encryption_key", "a-test-encryption-secret-of-32-chars!!")
    monkeypatch.setattr(settings, "frontend_url", "http://panel.test")

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_transport] = lambda: httpx.MockTransport(fake_tn.handler)
    app.state.session_maker = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


def make_product(pid: int, name: str, variants: list[dict], published: bool = True) -> dict:
    return {"id": pid, "name": {"es": name}, "published": published, "variants": variants}
