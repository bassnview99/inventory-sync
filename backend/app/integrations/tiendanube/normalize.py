"""Convierte productos de Tiendanube en filas planas de variantes. Sin E/S: fácil de probar."""
from dataclasses import dataclass

LANG_PREFERENCE = ("es", "pt", "en")


def localized(value) -> str:
    """Tiendanube devuelve textos como {"es": "Remera", "pt": "Camiseta"}."""
    if isinstance(value, dict):
        for lang in LANG_PREFERENCE:
            if value.get(lang):
                return str(value[lang]).strip()
        for text in value.values():
            if text:
                return str(text).strip()
        return ""
    return str(value).strip() if value else ""


@dataclass(frozen=True)
class NormalizedVariant:
    external_product_id: str
    external_variant_id: str
    product_name: str
    variant_name: str | None
    sku: str | None
    stock: int | None
    inventory_levels: list[dict] | None
    published: bool


def _variant_name(variant: dict) -> str | None:
    values = [localized(v) for v in (variant.get("values") or [])]
    values = [v for v in values if v]
    return " / ".join(values) if values else None


def _stock(variant: dict) -> tuple[int | None, list[dict] | None]:
    levels = variant.get("inventory_levels")
    if levels:
        clean = [{"location_id": str(lv.get("location_id")), "stock": lv.get("stock")} for lv in levels]
        known = [lv["stock"] for lv in clean if isinstance(lv["stock"], int)]
        # Con multi-inventario `stock` del nivel puede ser null (sin control): total solo si hay algún dato.
        return (sum(known) if known else None), clean
    stock = variant.get("stock")
    return (stock if isinstance(stock, int) else None), None


def normalize_product(product: dict) -> list[NormalizedVariant]:
    name = localized(product.get("name")) or f"Producto {product.get('id')}"
    rows = []
    for variant in product.get("variants") or []:
        sku = (variant.get("sku") or "").strip() or None  # se conserva el valor original; solo se descartan vacíos
        stock, levels = _stock(variant)
        rows.append(NormalizedVariant(
            external_product_id=str(product["id"]),
            external_variant_id=str(variant["id"]),
            product_name=name[:300],
            variant_name=(_variant_name(variant) or None),
            sku=sku[:160] if sku else None,
            stock=stock,
            inventory_levels=levels,
            published=bool(product.get("published", True)),
        ))
    return rows
