# Política de sincronización (diseño)

## Importación inicial de ambas plataformas

1. Obtener inventario y catálogo desde Tiendanube.
2. Obtener publicaciones y variantes elegibles desde Mercado Libre.
3. Persistir snapshots por separado; todavía no escribir cantidades.
4. Proponer asociaciones por SKU normalizado.
5. Enviar coincidencias ambiguas, SKU duplicados o variantes sin SKU a revisión manual.
6. El administrador confirma mappings.
7. Solo después de la confirmación, habilitar sincronización para esa variante.

**No se elige automáticamente una plataforma como ganadora en la importación inicial.** Si las cantidades difieren, la diferencia queda en revisión para que el usuario defina el stock de partida.

## Eventos y concurrencia

- Validar firma/autenticidad con el mecanismo oficial que documente cada plataforma.
- Persistir el webhook antes de responder éxito.
- Deduplicar por identificador estable; si no existe, usar huella determinista del payload y ventana documentada, sin fingir garantía perfecta.
- Encolar trabajo y serializar por `variant_id`.
- Reconsultar el estado actual en la plataforma de origen antes de decidir.
- No aplicar una observación si se demuestra que es anterior a otra observación comparable.
- Si no existe versión/timestamp comparable, aplicar reconciliación conservadora y registrar ambigüedad.
- Guardar el resultado de cada intento y verificar el destino cuando la API lo permita.

## Evitar ciclos

Cada operación interna tendrá un `operation_id`/correlation ID. El worker registra el cambio esperado y, si la plataforma destino emite un webhook como consecuencia, el evento se reconoce como eco cuando los datos disponibles permiten vincularlo con la operación. No se dependerá únicamente de una ventana temporal.

## Ventas simultáneas

No existe transacción distribuida entre ambas plataformas. Una venta simultánea puede ocurrir antes de que el otro canal reciba la actualización. Se mitiga con:
- trabajos serializados por variante;
- procesamiento rápido;
- relectura del stock actual;
- política opcional de stock de seguridad;
- alertas de divergencia y reconciliación periódica.

La garantía de no sobreventa absoluta requeriría que ambos canales compartieran una reserva atómica o que uno de ellos no vendiera de forma independiente; no debe prometerse con webhooks solamente.

## Reintentos

Reintentar errores de red, 429 y 5xx con backoff exponencial y jitter, respetando `Retry-After` cuando exista. No reintentar indefinidamente errores permanentes de permisos, validación o recursos inexistentes. La política exacta de rate limits se implementará según documentación oficial.

## No-go

No modificar precios, títulos, descripciones, fotos, estado de publicación ni crear publicaciones. Solo inventario de variantes previamente asociadas y habilitadas.
