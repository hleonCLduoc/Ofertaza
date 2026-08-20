import html
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "surprice"

CATEGORIES = [
    "zapatillas",
    "chaquetas",
    "polerones",
    "mochilas",
]

SEARCH_URL = "https://www.surprice.cl/catalogsearch/result/"
PAGE_SIZE = 36

TILE_RE = re.compile(r'data-product-id="(\d+)"')
HREF_NAME_RE = re.compile(r'class="product-item-link"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')
IMG_RE = re.compile(r'class="product-image-photo"\s+src="([^"]+)"')
BRAND_RE = re.compile(r'itemprop="marca">([^<]+)</div>')
FINAL_PRICE_RE = re.compile(r'data-price-amount="(\d+)"\s+data-price-type="finalPrice"')
OLD_PRICE_RE = re.compile(r'data-price-amount="(\d+)"\s+data-price-type="oldPrice"')
TOTAL_RE = re.compile(r'toolbar-number">[\d,]+</span>-<span class="toolbar-number">[\d,]+</span> de <span class="toolbar-number">([\d,]+)</span>')

logger = logging.getLogger("sites.surprice")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    resp = session.get(SEARCH_URL, params={"q": term, "p": page}, timeout=20)
    resp.raise_for_status()
    total_match = TOTAL_RE.search(resp.text)
    total = int(total_match.group(1).replace(",", "")) if total_match else 0
    return {"html": resp.text, "total": total}


def get_pagination(page_data):
    return page_data.get("total", 0), PAGE_SIZE


def _tiles(page_html):
    matches = list(TILE_RE.finditer(page_html))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(page_html)
        yield m.group(1), page_html[start:end]


def iter_products(page_data):
    page_html = page_data.get("html", "")
    for pid, tile_html in _tiles(page_html):
        name_match = HREF_NAME_RE.search(tile_html)
        img_match = IMG_RE.search(tile_html)
        brand_match = BRAND_RE.search(tile_html)
        final_match = FINAL_PRICE_RE.search(tile_html)

        if not final_match:
            continue
        internet_price = int(final_match.group(1))
        if internet_price <= 0:
            continue

        prices = {"internetPrice": internet_price}
        discount_percent = None
        old_match = OLD_PRICE_RE.search(tile_html)
        if old_match:
            normal_price = int(old_match.group(1))
            if normal_price > internet_price:
                prices["normalPrice"] = normal_price
                discount_percent = round((1 - internet_price / normal_price) * 100)

        yield {
            "sku_id": pid,
            "product_id": pid,
            "display_name": html.unescape(name_match.group(2)) if name_match else "",
            "brand": brand_match.group(1) if brand_match else "",
            "seller_id": "",
            "seller_name": "Surprice",
            "url": name_match.group(1) if name_match else "",
            "media_url": img_match.group(1) if img_match else None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
