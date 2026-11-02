# Roadmap

## Etapa 1 — Arquitectura y persistencia
- [x] Esqueleto modular FastAPI / React.
- [x] Modelos SQLAlchemy.
- [x] Migración inicial Alembic.
- [x] Docker Compose para desarrollo.
- [x] Pruebas base y documentación.
- [ ] Revisar y ejecutar migración contra PostgreSQL en el entorno del usuario.

## Etapa 2 — Tiendanube
- [x] Revisar documentación oficial vigente: OAuth, scopes, variantes, stock, ubicaciones, límites. (Webhooks: etapa 6.)
- [ ] Registrar aplicación y callback (lo haces tú en el panel de socios de Tiendanube).
- [x] Implementar OAuth state/CSRF (state de un solo uso, caduca en 10 min) y almacenamiento cifrado.
- [x] Cliente HTTP con timeout, retry (429/5xx, respeta X-Rate-Limit-Reset) y paginación por Link.
- [x] Importación de catálogo de solo lectura, con historial de trabajos y errores.
- [x] Pruebas con respuestas mock (escritas; ejecútalas con `pytest -q`).
- [ ] Probar con una tienda real y confirmar la cabecera del token.

## Etapa 3 — Mercado Libre
- [ ] Revisar documentación oficial vigente: OAuth, permisos, publicaciones, variaciones, inventario y notificaciones.
- [ ] Registrar aplicación y callback.
- [ ] Implementar OAuth state/CSRF y refresh token.
- [ ] Cliente HTTP y pruebas mock.

## Etapa 4 — Importación y matching
- [ ] Importar catálogo de ambas plataformas sin escribir stock.
- [ ] Normalizar SKU conservando valor original.
- [ ] Proponer matching exacto y mostrar conflictos.
- [ ] Confirmación manual de mappings.

## Etapa 5 — Motor de inventario
- [ ] Definir semántica de cantidad por plataforma.
- [ ] Política de stock inicial.
- [ ] Bloqueos por variante y outbox.
- [ ] Escritura de inventario permitida y verificación.
- [ ] Movimientos y auditoría.

## Etapa 6 — Webhooks
- [ ] Validación oficial de autenticidad.
- [ ] Inbox idempotente.
- [ ] Procesamiento asíncrono.
- [ ] Reintentos y reconciliación periódica.

## Etapa 7 — Panel
- [ ] Login y roles.
- [ ] Estado de conexiones.
- [ ] Catálogo, mappings y diferencias.
- [ ] Acciones manuales auditadas.

## Etapa 8 — Producción
- [ ] Pruebas contractuales e integrales.
- [ ] Rate limits y observabilidad.
- [ ] Backups y restauración probada.
- [ ] HTTPS, secretos, monitoreo y despliegue.
