import logging

import requests

from config import USER_AGENT

SITE_ID = "preunic"

CATEGORIES = [
    "shampoo",
    "maquillaje",
    "protector solar",
    "perfume",
]

SEARCH_URL = "https://api.empathy.co/search/v1/query/preunic/search"
PAGE_SIZE = 40

logger = logging.getLogger("sites.preunic")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    start = (page - 1) * PAGE_SIZE
    resp = session.get(
        SEARCH_URL,
        params={
            "query": term,
            "lang": "es",
            "scope": "desktop",
            "currency": "CLP",
            "rows": PAGE_SIZE,
            "start": start,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        logger.warning("HTTP %s para %r página %s", resp.status_code, term, page)
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("JSON inválido para %r página %s", term, page)
        return None


def get_pagination(page_data):
    catalog = page_data.get("catalog", {})
    pagination = catalog.get("pagination", {})
    return pagination.get("total", 0), pagination.get("rows", PAGE_SIZE) or PAGE_SIZE


def iter_products(page_data):
    catalog = page_data.get("catalog", {})
    for product in catalog.get("content", []):
        sku_id = product.get("sku") or product.get("id")
        if not sku_id:
            continue

        offer_price = product.get("offerPrice")
        normal_price = product.get("price")
        card_price = product.get("cardPrice")
        if offer_price is None:
            continue

        prices = {"internetPrice": int(offer_price)}
        discount_percent = None
        if normal_price and normal_price > offer_price:
            prices["normalPrice"] = int(normal_price)
            discount_percent = round((1 - offer_price / normal_price) * 100)
        if card_price and card_price != offer_price:
            prices["cmrPrice"] = int(card_price)

        slug = product.get("slug", "")
        url = f"https://preunic.cl/products/{slug}" if slug else ""

        yield {
            "sku_id": str(sku_id),
            "product_id": str(product.get("id", sku_id)),
            "display_name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "seller_id": "",
            "seller_name": "Preunic",
            "url": url,
            "media_url": product.get("image"),
            "prices": prices,
            "discount_percent": discount_percent,
        }
