import json
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "sodimac"

CATEGORIES = [
    "taladro",
    "pintura interior",
]

SEARCH_URL = "https://www.sodimac.cl/sodimac-cl/search"

NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

logger = logging.getLogger("sites.sodimac")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# El buscador de Sodimac redirige el término (?Ntt=) a una URL de categoría
# fija (ej. /sodimac-cl/lista/cat14080023/Taladros); la paginación (?page=N)
# solo funciona sobre esa URL ya resuelta, no sobre el buscador original.
_category_url_cache = {}


def _parse_next_data(html):
    match = NEXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data.get("props", {}).get("pageProps", {})


def _resolve_category_url(term):
    if term in _category_url_cache:
        return _category_url_cache[term]

    resp = session.get(SEARCH_URL, params={"Ntt": term}, timeout=20)
    resp.raise_for_status()
    url = resp.url.split("?")[0]
    _category_url_cache[term] = url
    return url


def fetch_page(term, page):
    base_url = _resolve_category_url(term)
    resp = session.get(base_url, params={"page": page}, timeout=20)
    resp.raise_for_status()
    page_data = _parse_next_data(resp.text)
    if page_data is None:
        logger.warning("No se encontró __NEXT_DATA__ para %r página %s", term, page)
    return page_data


def get_pagination(page_data):
    pagination = page_data.get("pagination", {})
    return pagination.get("count", 0), pagination.get("perPage", 48) or 48


def _parse_price(price_field):
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
