# Modelo de datos

## Entidades

- `stores`: tienda lógica del usuario.
- `platform_connections`: conexión por plataforma y tienda. `credentials_encrypted` almacena un sobre cifrado, nunca texto plano.
- `products`: producto interno.
- `product_variants`: unidad sincronizable; el SKU se normaliza en servicios, no se impone unicidad global.
- `product_mappings`: asociación entre variante interna y recurso externo.
- `inventory_levels`: última observación conocida de cantidad por plataforma/ubicación.
- `inventory_movements`: historial append-only de cambios observados o aplicados.
- `webhook_events`: bandeja de entrada idempotente.
- `sync_jobs`: trabajos durables y reintentables.
- `sync_logs`: resultado técnico por intento.
- `audit_logs`: acciones administrativas y cambios relevantes.

## Restricciones clave

- Una conexión por tienda y plataforma.
- Una asociación externa por plataforma, tienda y variante externa.
- Un nivel de inventario por variante, plataforma y ubicación externa.
- Deduplicación por plataforma, tienda y `external_event_id` cuando el proveedor entregue un ID estable.
- Los movimientos son históricos: corregir significa insertar un ajuste, no reescribir el pasado.

## Notas de inventario

`quantity` representa la cantidad disponible reportada por el conector para esa ubicación. La semántica exacta de disponible, reservado, fulfillment y depósitos debe verificarse por plataforma antes de implementar los conectores. No asumir que `available = stock - reserved` hasta validar el contrato de ambas APIs.

`observed_at` es el momento en que el backend obtuvo la observación. `source_updated_at` es opcional y solo se utilizará si la API proporciona una marca de tiempo con semántica documentada. No comparar relojes de plataformas como si fueran un contador de versión común.
