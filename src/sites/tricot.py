import html
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "tricot"

CATEGORIES = [
    "vestido",
    "polera",
    "jeans",
    "zapatos",
]

GRID_URL = "https://www.tricot.cl/on/demandware.store/Sites-TRICOT_CL-Site/es_CL/Search-ShowAjax"
SEARCH_URL = "https://www.tricot.cl/resultado-busqueda"
PAGE_SIZE = 24

TILE_ANCHOR_RE = re.compile(r'data-pid="(\w+)"')
HREF_RE = re.compile(r'href="([^"]+\.html)"')
IMG_RE = re.compile(r'<img src="(https://www\.tricot\.cl/dw/image[^"]+)"')
ALT_RE = re.compile(r'alt="([^"]+)"')
SALES_PRICE_RE = re.compile(r'tri-sales[\s\S]{0,300}?content="([\d.]+)"')
LIST_PRICE_RE = re.compile(r'strike-through value" content="([\d.]+)"')
TOTAL_RE = re.compile(r'js-result-qty" value="(\d+)"')

logger = logging.getLogger("sites.tricot")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

_total_cache = {}


def _resolve_total(term):
    if term in _total_cache:
        return _total_cache[term]
    resp = session.get(SEARCH_URL, params={"q": term}, timeout=20)
    resp.raise_for_status()
    match = TOTAL_RE.search(resp.text)
    total = int(match.group(1)) if match else 0
    _total_cache[term] = total
    return total


def fetch_page(term, page):
    total = _resolve_total(term)
    start = (page - 1) * PAGE_SIZE
    resp = session.get(GRID_URL, params={"q": term, "start": start, "sz": PAGE_SIZE}, timeout=20)
    resp.raise_for_status()
    return {"html": resp.text, "total": total}


def get_pagination(page_data):
    return page_data.get("total", 0), PAGE_SIZE


def _tiles(page_html):
    matches = list(TILE_ANCHOR_RE.finditer(page_html))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(page_html)
        yield m.group(1), page_html[start:end]


def iter_products(page_data):
    page_html = page_data.get("html", "")
    for pid, tile_html in _tiles(page_html):
        href_match = HREF_RE.search(tile_html)
        img_match = IMG_RE.search(tile_html)
        alt_match = ALT_RE.search(tile_html)
        sales_match = SALES_PRICE_RE.search(tile_html)
        list_match = LIST_PRICE_RE.search(tile_html)

        if not sales_match:
            continue
        internet_price = int(float(sales_match.group(1)))
        if internet_price <= 0:
            continue

        prices = {"internetPrice": internet_price}
        discount_percent = None
        if list_match:
            normal_price = int(float(list_match.group(1)))
            if normal_price > internet_price:
                prices["normalPrice"] = normal_price
                discount_percent = round((1 - internet_price / normal_price) * 100)

        url = f"https://www.tricot.cl{href_match.group(1)}" if href_match else ""

        yield {
            "sku_id": pid,
            "product_id": pid,
            "display_name": html.unescape(alt_match.group(1)) if alt_match else "",
            "brand": "",
            "seller_id": "",
            "seller_name": "Tricot",
            "url": url,
            "media_url": img_match.group(1) if img_match else None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
