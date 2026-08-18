import logging

import requests

from config import USER_AGENT

SITE_ID = "jumbo"

CATEGORIES = [
    "arroz",
    "aceite",
    "detergente",
    "papel higienico",
]

# Jumbo (Cencosud) usa Constructor.io como buscador. La key va expuesta en el
# frontend (es de solo-lectura para búsquedas), así que se llama directo.
SEARCH_URL = "https://ac.cnstrc.com/search"
KEY = "key_JopvNXKS61kwGkBe"
PAGE_SIZE = 40

logger = logging.getLogger("sites.jumbo")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    resp = session.get(
        f"{SEARCH_URL}/{term}",
        params={"key": KEY, "page": page, "num_results_per_page": PAGE_SIZE},
        timeout=20,
    )
    if resp.status_code != 200:
        logger.warning("HTTP %s para %r página %s", resp.status_code, term, page)
        return None
    try:
        data = resp.json()
    except ValueError:
        logger.warning("JSON inválido para %r página %s", term, page)
        return None
    return data.get("response", {})


def get_pagination(page_data):
    return page_data.get("total_num_results", 0), PAGE_SIZE


def iter_products(page_data):
    for result in page_data.get("results", []):
        data = result.get("data", {})
        sku_id = data.get("id") or data.get("productId")
        if not sku_id:
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
        seller_name = sellers[0] if isinstance(sellers, list) and sellers else "Jumbo"

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
