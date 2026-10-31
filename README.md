# Inventory Sync — Tiendanube + Mercado Libre

Middleware propio para reconciliar inventario entre una tienda Tiendanube y una cuenta de Mercado Libre. Esta entrega implementa **Etapa 1: arquitectura, modelo de datos, migración inicial, configuración local, documentación y pruebas base**.

> No conecta todavía con las API externas ni modifica publicaciones. OAuth, webhooks e inventario real se implementarán en etapas posteriores, después de verificar los contratos oficiales vigentes.

## Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x async
- PostgreSQL 16
- Alembic
- Redis (reservado para la cola de trabajos)
- React + Vite (esqueleto del panel)
- Docker Compose
- Pytest

## Requisitos

- Docker Desktop / Docker Engine + Compose
- Git
- Opcional para desarrollo local: Python 3.12+ y Node.js 20+

## Inicio rápido

1. Copia `.env.example` como `.env`.
2. Cambia `APP_SECRET_KEY` y `TOKEN_ENCRYPTION_KEY` antes de usar datos reales.
3. Ejecuta:

```bash
docker compose up --build
```

4. Comprueba:
   - API: http://localhost:8000/health
   - Documentación OpenAPI: http://localhost:8000/docs
   - Frontend: http://localhost:5173

La API arranca sin credenciales de Tiendanube ni Mercado Libre. Es intencional: las conexiones se incorporan en las etapas 2 y 3.

## Migraciones

En otro terminal:

```bash
docker compose exec backend alembic upgrade head
```

Para crear una migración después de modificar modelos:

```bash
docker compose exec backend alembic revision --autogenerate -m "descripcion"
docker compose exec backend alembic upgrade head
```

Revisa siempre las migraciones generadas antes de aplicarlas en producción.

## Pruebas

Local:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Las pruebas de esta etapa usan SQLite en memoria para validar el modelo y endpoints sin exigir servicios externos. PostgreSQL sigue siendo la base de datos objetivo.

## Decisiones de esta etapa

- Se conserva `stores` aunque inicialmente exista una sola tienda; esto evita una migración estructural si el producto crece.
- El inventario se guarda por variante, plataforma y ubicación externa.
- Las asociaciones de producto son explícitas; SKU ayuda a proponer coincidencias, pero no se presupone que sea globalmente único.
- Webhooks y trabajos tienen identificadores idempotentes y estados persistidos.
- Las credenciales OAuth se almacenarán cifradas en backend; no se implementa todavía el cifrado ni OAuth.
- El panel no contiene secretos ni llamadas directas a plataformas.

## Estructura

```text
inventory-sync/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── database/
│   │   ├── integrations/       # conectores de etapas 2 y 3
│   │   ├── services/            # dominio y reconciliación
│   │   ├── webhooks/
│   │   ├── workers/
│   │   ├── config.py
│   │   ├── main.py
│   │   └── models.py
│   ├── alembic/
│   ├── tests/
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
├── docs/
├── docker-compose.yml
└── .env.example
```

## Estado de implementación

| Etapa | Estado |
|---|---|
| 1. Arquitectura, base de datos y documentación | Implementación inicial entregada |
| 2. Tiendanube OAuth/API | Pendiente de verificación documental |
| 3. Mercado Libre OAuth/API | Pendiente de verificación documental |
| 4. Importación y asociación por SKU | Pendiente |
| 5. Sincronización y movimientos | Pendiente |
| 6. Webhooks e idempotencia operativa | Pendiente |
| 7. Panel administrativo | Esqueleto inicial |
| 8. Pruebas integrales y despliegue | Pendiente |

## Seguridad

No subas `.env`, tokens, secretos, dumps de base de datos ni credenciales al repositorio. En producción utiliza un gestor de secretos, TLS, copias de seguridad y rotación de claves. No expongas PostgreSQL ni Redis a Internet.
