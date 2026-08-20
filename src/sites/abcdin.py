import html
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "abcdin"

CATEGORIES = [
    "notebook",
    "celular",
    "refrigerador",
    "cama europea 1.5 plazas",
    "cama europea 2 plazas",
    "cama king size",
    "cama",
    "frazadas",
    "sabanas",
    "tv",
]

GRID_URL = "https://www.abc.cl/on/demandware.store/Sites-Abc-Site/es_CL/Search-UpdateGrid"
PAGE_SIZE = 36

# No se usa el conteo real (viene en la página de búsqueda normal, no en
# este fragmento AJAX); se estima grande y se corta con página vacía
# (ver engine._process_page) o al llegar a MAX_PAGES_PER_TERM.
ESTIMATED_TOTAL = 2000

TILE_ANCHOR_RE = re.compile(r'class="product-tile__wrapper" data-pid="(\w+)"')
HREF_RE = re.compile(r'href="([^"]+\.html)"')
IMG_RE = re.compile(r'<img[^>]*src="(https://www\.abc\.cl/dw/image[^"]+)"')
INTERNET_PRICE_RE = re.compile(r'js-internet-price[\s\S]{0,400}?data-value="([\d.]+)"')
NORMAL_PRICE_RE = re.compile(r'js-normal-price[\s\S]{0,600}?data-value="([\d.]+)"')
# El bloque data-gtm-click="{...}" va embebido como atributo HTML, así que
# sus comillas internas están codificadas como &quot; en vez de ".
NAME_RE = re.compile(r"&quot;name&quot;:&quot;(.*?)&quot;")
BRAND_RE = re.compile(r"&quot;brand&quot;:&quot;(.*?)&quot;")

logger = logging.getLogger("sites.abcdin")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    start = (page - 1) * PAGE_SIZE
    resp = session.get(GRID_URL, params={"q": term, "start": start, "sz": PAGE_SIZE}, timeout=20)
    resp.raise_for_status()
    return {"html": resp.text}


def get_pagination(page_data):
    return ESTIMATED_TOTAL, PAGE_SIZE


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
        name_match = NAME_RE.search(tile_html)
        brand_match = BRAND_RE.search(tile_html)
        internet_match = INTERNET_PRICE_RE.search(tile_html)
        normal_match = NORMAL_PRICE_RE.search(tile_html)

        internet_price = int(float(internet_match.group(1))) if internet_match else None
        if internet_price is None or internet_price <= 0:
            continue

        prices = {"internetPrice": internet_price}
        discount_percent = None
        if normal_match:
            normal_price = int(float(normal_match.group(1)))
            if normal_price > internet_price:
                prices["normalPrice"] = normal_price
                discount_percent = round((1 - internet_price / normal_price) * 100)

        url = f"https://www.abc.cl{href_match.group(1)}" if href_match else ""

        yield {
            "sku_id": pid,
            "product_id": pid,
            "display_name": html.unescape(name_match.group(1)) if name_match else "",
            "brand": html.unescape(brand_match.group(1)) if brand_match else "",
            "seller_id": "",
            "seller_name": "ABCDIN",
            "url": url,
            "media_url": img_match.group(1) if img_match else None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
