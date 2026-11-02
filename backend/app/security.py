import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException, status

from app.config import DEV_PLACEHOLDERS, settings


def _fernet() -> Fernet:
    key = settings.token_encryption_key
    if settings.is_production and (key in DEV_PLACEHOLDERS or len(key) < 32):
        raise RuntimeError("TOKEN_ENCRYPTION_KEY debe ser un secreto propio de al menos 32 caracteres en producción.")
    # Se deriva una clave Fernet válida de 32 bytes a partir del secreto configurado.
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_credentials(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("ascii")


def decrypt_credentials(token: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(token.encode("ascii")))
    except InvalidToken as exc:
        raise ValueError("No se pudieron descifrar las credenciales (¿cambió TOKEN_ENCRYPTION_KEY?).") from exc


def new_state() -> str:
    return secrets.token_urlsafe(32)


async def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """Protege la API administrativa hasta que exista login real (etapa 7)."""
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_API_KEY no está configurada en el servidor.")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clave de administración inválida.")
