import json
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "ripley"

CATEGORIES = [
    "notebook",
    "celular",
    "smartphone",
    "computador",
]

BASE_URL = "https://simple.ripley.cl/search"

NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

logger = logging.getLogger("sites.ripley")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text


def fetch_page(term, page):
    url = f"{BASE_URL}/{term}"
    resp = session.get(url, params={"sort": "relevance_desc", "page": page}, timeout=20)
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
    findability = data.get("props", {}).get("pageProps", {}).get("findabilityProps", {})
    return findability.get("data")


def get_pagination(page_data):
    return page_data.get("total", 0), page_data.get("limit", 48) or 48


def _parse_price(price_str):
    if not price_str:
        return None
    digits = re.sub(r"[^\d]", "", price_str)
    return int(digits) if digits else None


def iter_products(page_data):
    for product in page_data.get("products", []):
        sku_id = product.get("sku")
        if not sku_id:
            continue

        prices = {}
        old_price = _parse_price(product.get("oldPrice"))
        if old_price is not None:
            prices["normalPrice"] = old_price

        internet_price = product.get("priceNumber") or _parse_price(product.get("price"))
        if internet_price is not None:
            prices["internetPrice"] = internet_price

        card_price = _parse_price(product.get("ripleyPrice"))
        if card_price is not None:
            prices["cmrPrice"] = card_price

        product_id = str(product.get("parentProductID") or product.get("code") or "")
        name = product.get("name", "")
        slug = _slugify(name)
        url_id = product_id.lower()
        url = f"https://simple.ripley.cl/{slug}-{url_id}" if slug and url_id else ""

        shop = product.get("shop") or {}

        yield {
            "sku_id": str(sku_id),
            "product_id": product_id,
            "display_name": name,
            "brand": product.get("brand", ""),
            "seller_id": str(shop.get("sellerId", "")),
            "seller_name": shop.get("shopName") or product.get("seller", ""),
            "url": url,
            "media_url": product.get("primaryImage"),
            "prices": prices,
            "discount_percent": product.get("discount"),
        }
