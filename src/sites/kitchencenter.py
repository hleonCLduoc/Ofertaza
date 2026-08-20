import html
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "kitchencenter"

CATEGORIES = [
    "licuadora",
    "refrigerador",
    "horno",
    "cafetera",
    "batidora",
    "aspiradora",
    "freidora de aire",
    "hervidor",
    "microondas",
    "lavavajillas",
    "ollas",
    "sartenes",
    "tostador",
    "plancha",
]

SEARCH_URL = "https://www.kitchencenter.cl/search"
PAGE_SIZE = 24

TOTAL_RE = re.compile(r"([\d.,]+)\s*resultados encontrados")
HEADING_RE = re.compile(
    r'class="card__heading"[\s\S]{0,150}?href="([^"?]+)[^"]*"'
    r'[\s\S]{0,150}?StandardCardNoMediaLink--(\d+)[\s\S]{0,300}?>\s*([^<]+?)\s*</a>'
)
SALE_PRICE_RE = re.compile(r'price-item price-item--sale[^"]*">\s*\$([\d.,]+)')
REGULAR_PRICE_RE = re.compile(r'price-item price-item--regular"[^>]*>\s*\$([\d.,]+)')

logger = logging.getLogger("sites.kitchencenter")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _parse_price(text):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def fetch_page(term, page):
    resp = session.get(
        SEARCH_URL, params={"q": term, "type": "product", "page": page}, timeout=20
    )
    resp.raise_for_status()
    total_match = TOTAL_RE.search(resp.text)
    total = _parse_price(total_match.group(1)) if total_match else 0
    return {"html": resp.text, "total": total or 0}


def get_pagination(page_data):
    return page_data.get("total", 0), PAGE_SIZE


def iter_products(page_data):
    page_html = page_data.get("html", "")
    headings = list(HEADING_RE.finditer(page_html))
    for i, m in enumerate(headings):
        handle, product_id, name = m.group(1), m.group(2), m.group(3)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else min(len(page_html), start + 3000)
        tile_html = page_html[start:end]

        sale_match = SALE_PRICE_RE.search(tile_html)
        if not sale_match:
            continue
        internet_price = _parse_price(sale_match.group(1))
        if not internet_price:
            continue

        prices = {"internetPrice": internet_price}
        discount_percent = None
        regular_match = REGULAR_PRICE_RE.search(tile_html)
        if regular_match:
            normal_price = _parse_price(regular_match.group(1))
            if normal_price and normal_price > internet_price:
                prices["normalPrice"] = normal_price
                discount_percent = round((1 - internet_price / normal_price) * 100)

        yield {
            "sku_id": product_id,
            "product_id": product_id,
            "display_name": html.unescape(name),
            "brand": "",
            "seller_id": "",
            "seller_name": "Kitchen Center",
            "url": f"https://www.kitchencenter.cl{handle}",
            "media_url": None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
