"""Cliente HTTP de Tiendanube (solo lectura en esta etapa).

Referencias oficiales:
- OAuth: https://tiendanube.github.io/api-documentation/authentication
- Límites: bucket de 40 solicitudes que se vacía a 2/s; 429 al excederlo. Cabeceras X-Rate-Limit-*.
- Paginación: page (base 1), per_page hasta 200, cabecera Link con la URL de la página siguiente.
- Toda solicitud debe llevar User-Agent con nombre de la app y contacto (si no, 400).
"""
import asyncio
import random
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import httpx

from app.config import settings

# NOTA: el formato exacto de esta cabecera no figura en las páginas de documentación consultadas;
# Tiendanube documenta `Authentication: bearer <token>`. Verifícalo con la primera conexión real.
AUTH_HEADER = "Authentication"
MAX_RETRIES = 5
PAGE_SIZE = 200


class TiendanubeError(Exception):
    def __init__(self, message: str, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def build_authorize_url(state: str) -> str:
    if not settings.tiendanube_app_id:
        raise TiendanubeError("TIENDANUBE_APP_ID no está configurado.")
    base = f"{settings.tiendanube_auth_base}/apps/{settings.tiendanube_app_id}/authorize"
    return f"{base}?{urlencode({'state': state})}"


async def exchange_code(code: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Canjea el código de autorización (válido pocos minutos) por el token de acceso."""
    if not settings.tiendanube_app_id or not settings.tiendanube_client_secret:
        raise TiendanubeError("Faltan TIENDANUBE_APP_ID o TIENDANUBE_CLIENT_SECRET.")
    async with httpx.AsyncClient(timeout=20, transport=transport) as http:
        response = await http.post(
            f"{settings.tiendanube_auth_base}/apps/authorize/token",
            json={
                "client_id": settings.tiendanube_app_id,
                "client_secret": settings.tiendanube_client_secret,
                "grant_type": "authorization_code",
                "code": code,
            },
            headers={"User-Agent": settings.tiendanube_user_agent},
        )
    if response.status_code != 200:
        raise TiendanubeError(f"Tiendanube rechazó el código de autorización (HTTP {response.status_code}).", response.status_code)
    data = response.json()
    if not data.get("access_token") or data.get("user_id") is None:
        raise TiendanubeError("Respuesta de token incompleta.")
    return data


class TiendanubeClient:
    def __init__(self, store_id: str, access_token: str, transport: httpx.AsyncBaseTransport | None = None,
                 sleep=asyncio.sleep):
        self.store_id = str(store_id)
        self._sleep = sleep
        self._http = httpx.AsyncClient(
            base_url=f"{settings.tiendanube_api_base}/{self.store_id}",
            headers={
                AUTH_HEADER: f"bearer {access_token}",
                "User-Agent": settings.tiendanube_user_agent,
                "Content-Type": "application/json",
            },
            timeout=30,
            transport=transport,
        )

    async def __aenter__(self) -> "TiendanubeClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._http.request(method, url, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == MAX_RETRIES:
                    raise TiendanubeError(f"Error de red hablando con Tiendanube: {exc}", retryable=True) from exc
                await self._sleep(self._backoff(attempt))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_RETRIES:
                    raise TiendanubeError(
                        f"Tiendanube respondió HTTP {response.status_code} tras {MAX_RETRIES} reintentos.",
                        response.status_code, retryable=True,
                    )
                await self._sleep(self._retry_delay(response, attempt))
                continue
            return response
        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(30.0, 2 ** attempt) + random.uniform(0, 0.5)

    @classmethod
    def _retry_delay(cls, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.replace(".", "", 1).isdigit():
            return float(retry_after)
        reset_ms = response.headers.get("X-Rate-Limit-Reset")  # milisegundos hasta vaciar el bucket
        if response.status_code == 429 and reset_ms and reset_ms.isdigit():
            return int(reset_ms) / 1000 + 0.2
        return cls._backoff(attempt)

    async def iter_products(self) -> AsyncIterator[dict]:
        """Recorre todo el catálogo siguiendo la cabecera Link (no se construyen URLs a mano)."""
        url: str | None = "/products"
        params: dict | None = {"per_page": PAGE_SIZE}
        first = True
        while url:
            response = await self._request("GET", url, params=params)
            if response.status_code == 404 and first:
                return  # Tiendanube responde 404 cuando la tienda no tiene productos.
            if response.status_code in (401, 403):
                raise TiendanubeError("Tiendanube rechazó el token (¿falta el permiso read_products o se desinstaló la app?).",
                                      response.status_code)
            if response.status_code != 200:
                raise TiendanubeError(f"Error al leer productos (HTTP {response.status_code}).", response.status_code)
            first = False
            for product in response.json():
                yield product
            next_link = response.links.get("next")
            url = next_link["url"] if next_link else None
            params = None  # la URL de `next` ya trae sus parámetros
