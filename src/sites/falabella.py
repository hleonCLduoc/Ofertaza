import json
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "falabella"

CATEGORIES = [
    "notebook",
    "celular",
    "smartphone",
    "computador",
    "cama europea 1.5 plazas",
    "cama europea 2 plazas",
    "cama king size",
    "tv",
    "refrigerador",
    "lavadora",
    "microondas",
    "aire acondicionado",
    "audifonos",
]

BASE_URL = "https://www.falabella.com/falabella-cl/search"

NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

logger = logging.getLogger("sites.falabella")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    params = {"Ntt": term, "page": page}
    resp = session.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        logger.warning("No se encontró __NEXT_DATA__ para %r página %s", term, page)
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("__NEXT_DATA__ inválido para %r página %s", term, page)
        return None
    return data.get("props", {}).get("pageProps", {})


def get_pagination(page_data):
    pagination = page_data.get("pagination", {})
    return pagination.get("count", 0), pagination.get("perPage", 48) or 48


def _parse_price(price_field):
    """price_field es una lista tipo ['789.990'] -> 789990 (int)."""
    if not price_field:
        return None
    digits = re.sub(r"[^\d]", "", price_field[0])
    return int(digits) if digits else None


def _parse_discount_percent(discount_badge):
    if not discount_badge:
        return None
    label = discount_badge.get("label", "")
    match = re.search(r"(\d+)", label)
    return int(match.group(1)) if match else None


def iter_products(page_data):
    for product in page_data.get("results", []):
        sku_id = product.get("skuId") or product.get("productId")
        if not sku_id:
            continue

        prices = {}
        for entry in product.get("prices", []):
            price_type = entry.get("type")
            value = _parse_price(entry.get("price"))
            if price_type and value is not None:
                prices[price_type] = value

        media_urls = product.get("mediaUrls") or []

        yield {
            "sku_id": str(sku_id),
            "product_id": str(product.get("productId", "")),
            "display_name": product.get("displayName", ""),
            "brand": product.get("brand", ""),
            "seller_id": product.get("sellerId", ""),
            "seller_name": product.get("sellerName", ""),
            "url": product.get("url", ""),
            "media_url": media_urls[0] if media_urls else None,
            "prices": prices,
            "discount_percent": _parse_discount_percent(product.get("discountBadge")),
        }
