import logging

import requests

from config import USER_AGENT

SITE_ID = "theline"

CATEGORIES = [
    "zapatillas",
    "poleron",
    "chaqueta",
    "jockey",
    "jordan",
]

BASE_URL = "https://www.theline.cl/api/catalog_system/pub/products/search"
PAGE_SIZE = 50

logger = logging.getLogger("sites.theline")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE - 1
    resp = session.get(BASE_URL, params={"ft": term, "_from": start, "_to": end}, timeout=20)
    if resp.status_code not in (200, 206):
        logger.warning("HTTP %s para %r página %s", resp.status_code, term, page)
        return None
    try:
        products = resp.json()
    except ValueError:
        logger.warning("JSON inválido para %r página %s", term, page)
        return None

    resources = resp.headers.get("resources", "")
    total = len(products)
    if "/" in resources:
        try:
            total = int(resources.rsplit("/", 1)[-1])
        except ValueError:
            pass

    return {"products": products, "total": total}


def get_pagination(page_data):
    return page_data.get("total", 0), PAGE_SIZE


def iter_products(page_data):
    for product in page_data.get("products", []):
        link_text = product.get("linkText")
        url = f"https://www.theline.cl/{link_text}/p" if link_text else ""

        for item in product.get("items", []):
            sellers = item.get("sellers") or []
            seller = next((s for s in sellers if s.get("sellerDefault")), sellers[0] if sellers else None)
            if not seller:
                continue
            offer = seller.get("commertialOffer") or {}
            price = offer.get("Price")
            if price is None or price <= 0:
                continue
            list_price = offer.get("ListPrice")

            prices = {"internetPrice": int(round(price))}
            discount_percent = None
            if list_price and list_price > price:
                prices["normalPrice"] = int(round(list_price))
                discount_percent = round((1 - price / list_price) * 100)

            images = item.get("images") or []
            media_url = images[0].get("imageUrl") if images else None

            yield {
                "sku_id": str(item.get("itemId")),
                "product_id": str(product.get("productId", "")),
                "display_name": item.get("nameComplete") or product.get("productName", ""),
                "brand": product.get("brand", ""),
                "seller_id": str(seller.get("sellerId", "")),
                "seller_name": seller.get("sellerName", ""),
                "url": url,
                "media_url": media_url,
                "prices": prices,
                "discount_percent": discount_percent,
            }
