"""Lógica compartida para sitios del grupo Cencosud que usan Constructor.io
como buscador (Jumbo, Easy, Santa Isabel, ...). Cada sitio tiene su propia
key (de solo-lectura, expuesta en el frontend) pero la misma API."""

import requests

from config import USER_AGENT

SEARCH_URL = "https://ac.cnstrc.com/search"


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_page(session, key, page_size, term, page):
    resp = session.get(
        f"{SEARCH_URL}/{term}",
        params={"key": key, "page": page, "num_results_per_page": page_size},
        timeout=20,
    )
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    return data.get("response", {})


def get_pagination(page_data, page_size):
    return page_data.get("total_num_results", 0), page_size


def iter_products(page_data, default_seller):
    for result in page_data.get("results", []):
        data = result.get("data", {})
        sku_id = data.get("id") or data.get("productId")
        if not sku_id:
            continue

        name = result.get("value", "")
        if "granel" in name.lower():
            # Productos vendidos a peso variable: el precio de referencia
            # suele venir por kilo mientras el precio mostrado es de una
            # porción menor (250 g, 100 g, etc.), lo que genera falsas
            # alertas de "descuento" al comparar unidades distintas.
            continue

        selling_price = data.get("sellingPrice") or data.get("price")
        list_price = data.get("listPrice") or data.get("originalPrice")
        if selling_price is None:
            continue

        prices = {"internetPrice": int(selling_price)}
        discount_percent = None
        if list_price and list_price > selling_price:
            prices["normalPrice"] = int(list_price)
            discount_percent = round((1 - selling_price / list_price) * 100)

        brand = data.get("BrandName") or ""
        sellers = data.get("Vendido por")
        seller_name = sellers[0] if isinstance(sellers, list) and sellers else default_seller

        images = data.get("images") or []
        media_url = data.get("image_url") or (images[0] if images else None)

        yield {
            "sku_id": str(sku_id),
            "product_id": str(data.get("productId", sku_id)),
            "display_name": result.get("value", ""),
            "brand": brand,
            "seller_id": "",
            "seller_name": seller_name,
            "url": data.get("url", ""),
            "media_url": media_url,
            "prices": prices,
            "discount_percent": discount_percent,
        }
