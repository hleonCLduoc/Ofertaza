import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "marathon"

CATEGORIES = [
    "zapatillas",
    "poleron",
    "chaqueta",
    "mochila",
    "jordan",
]

SEARCH_URL = "https://www.marathon.cl/on/demandware.store/Sites-MarathonChile-Site/es_CL/Search-Show"
AJAX_URL = "https://www.marathon.cl/on/demandware.store/Sites-MarathonChile-Site/es_CL/Search-ShowAjax"
GRID_URL = "https://www.marathon.cl/on/demandware.store/Sites-MarathonChile-Site/es_CL/Search-UpdateGrid"
PAGE_SIZE = 24

TILE_RE = re.compile(
    r'<div class="product" data-pid="(\d+)">(.*?)(?=<div class="product" data-pid="|\Z)',
    re.DOTALL,
)
HREF_RE = re.compile(r'<a href="([^"]+\.html)"')
ALT_RE = re.compile(r'alt="([^"]+)"')
IMG_SRC_RE = re.compile(r'src="(https://www\.marathon\.cl/dw/image[^"]+)"')
PRICE_RE = re.compile(r"\$\s*([\d.]+)")
CGID_RE = re.compile(r"Search-UpdateGrid\?cgid=([A-Za-z0-9_-]+)")
TOTAL_RE = re.compile(r"([\d.,]+)\s*Resultados", re.IGNORECASE)

logger = logging.getLogger("sites.marathon")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# Algunos términos resuelven a una categoría fija (modo "grid" vía cgid),
# otros son búsqueda libre real (modo "ajax" vía Search-ShowAjax). Se cachea
# por proceso para no repetir la resolución en cada página/ciclo.
_resolution_cache = {}


def _parse_total(html):
    match = TOTAL_RE.search(html)
    if not match:
        return 0
    digits = re.sub(r"[^\d]", "", match.group(1))
    return int(digits) if digits else 0


def _resolve(term):
    if term in _resolution_cache:
        return _resolution_cache[term]

    probe = session.get(
        AJAX_URL, params={"q": term, "start": 0, "sz": PAGE_SIZE}, timeout=20, allow_redirects=False
    )
    if probe.status_code == 200 and 'data-pid="' in probe.text:
        result = ("ajax", None, _parse_total(probe.text))
        _resolution_cache[term] = result
        return result

    resp = session.get(SEARCH_URL, params={"q": term}, timeout=20)
    resp.raise_for_status()
    cgid_match = CGID_RE.search(resp.text)
    if cgid_match:
        result = ("grid", cgid_match.group(1), _parse_total(resp.text))
    else:
        result = (None, None, 0)
    _resolution_cache[term] = result
    return result


def fetch_page(term, page):
    kind, cgid, total = _resolve(term)
    if kind is None:
        logger.warning("No se pudo resolver búsqueda para %r", term)
        return None

    start = (page - 1) * PAGE_SIZE
    if kind == "ajax":
        resp = session.get(AJAX_URL, params={"q": term, "start": start, "sz": PAGE_SIZE}, timeout=20)
    else:
        resp = session.get(GRID_URL, params={"cgid": cgid, "start": start, "sz": PAGE_SIZE}, timeout=20)
    resp.raise_for_status()
    return {"html": resp.text, "total": total}


def get_pagination(page_data):
    return page_data.get("total", 0), PAGE_SIZE


def iter_products(page_data):
    html = page_data.get("html", "")
    for pid, tile_html in TILE_RE.findall(html):
        href_match = HREF_RE.search(tile_html)
        alt_match = ALT_RE.search(tile_html)
        img_match = IMG_SRC_RE.search(tile_html)
        prices_found = PRICE_RE.findall(tile_html)

        if not prices_found:
            continue

        sale_price = int(re.sub(r"[^\d]", "", prices_found[0]))
        prices = {"internetPrice": sale_price}
        discount_percent = None
        if len(prices_found) > 1:
            list_price = int(re.sub(r"[^\d]", "", prices_found[1]))
            if list_price > sale_price:
                prices["normalPrice"] = list_price
                discount_percent = round((1 - sale_price / list_price) * 100)

        url = f"https://www.marathon.cl{href_match.group(1)}" if href_match else ""

        yield {
            "sku_id": pid,
            "product_id": pid,
            "display_name": alt_match.group(1) if alt_match else "",
            "brand": "",
            "seller_id": "",
            "seller_name": "Marathon",
            "url": url,
            "media_url": img_match.group(1) if img_match else None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
