import html
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "hites"

CATEGORIES = [
    "notebook",
    "smartphone",
    "refrigeradores",
    "lavadoras",
]

GRID_URL = "https://www.hites.com/on/demandware.store/Sites-HITES-Site/es_CL/Search-ShowAjax"
PAGE_SIZE = 24

# No se encontró un total de resultados confiable en el HTML de Hites, así
# que se usa un estimado grande; el corte real ocurre cuando una página
# devuelve 0 productos (ver engine._process_page) o al llegar a
# config.MAX_PAGES_PER_TERM.
ESTIMATED_TOTAL = 2000

TILE_RE = re.compile(
    r'data-url="[^"]*Product-Variation\?pid=(\w+)" data-pid="\1">(.*?)'
    r'(?=data-url="[^"]*Product-Variation\?pid=\w+" data-pid="\w+">|\Z)',
    re.DOTALL,
)
HREF_RE = re.compile(r'<a class="image-item js-tile-image-container" href="([^"]+)"')
ALT_RE = re.compile(r'alt="([^"]+)"')
IMG_RE = re.compile(r'src="(https://www\.hites\.com/dw/image[^"]+)"')

# Precios anclados a su bloque específico (evita capturar montos de cuotas
# u otro texto suelto que también use "$"). "sales"/"list" traen un atributo
# content="NNNNNN" limpio; "hites-price" (tarjeta) no, así que se parsea el
# primer "$" dentro de su bloque.
CARD_PRICE_RE = re.compile(r'class="price-item hites-price">.*?\$\s*([\d.]+)', re.DOTALL)
SALE_PRICE_RE = re.compile(r'class="price-item sales strike-through">.*?content="(\d+)"', re.DOTALL)
LIST_PRICE_RE = re.compile(r'class="price-item list strike-through[^"]*">.*?content="(\d+)"', re.DOTALL)
ANY_CONTENT_PRICE_RE = re.compile(r'content="(\d+)"')

logger = logging.getLogger("sites.hites")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    start = (page - 1) * PAGE_SIZE
    resp = session.get(GRID_URL, params={"cgid": term, "start": start, "sz": PAGE_SIZE}, timeout=20)
    resp.raise_for_status()
    return {"html": resp.text}


def get_pagination(page_data):
    return ESTIMATED_TOTAL, PAGE_SIZE


def iter_products(page_data):
    page_html = page_data.get("html", "")
    for pid, tile_html in TILE_RE.findall(page_html):
        href_match = HREF_RE.search(tile_html)
        alt_match = ALT_RE.search(tile_html)
        img_match = IMG_RE.search(tile_html)

        card_match = CARD_PRICE_RE.search(tile_html)
        sale_match = SALE_PRICE_RE.search(tile_html)
        list_match = LIST_PRICE_RE.search(tile_html)

        card_price = int(re.sub(r"[^\d]", "", card_match.group(1))) if card_match else None
        sale_price = int(sale_match.group(1)) if sale_match else None
        list_price = int(list_match.group(1)) if list_match else None

        if sale_price is None:
            # Sin descuento vigente: no hay bloque "sales", se usa el
            # primer precio con atributo content= como precio base.
            fallback = ANY_CONTENT_PRICE_RE.search(tile_html)
            if fallback:
                sale_price = int(fallback.group(1))

        if sale_price is None or sale_price <= 0:
            continue

        prices = {"internetPrice": sale_price}
        discount_percent = None
        if list_price and list_price > sale_price:
            prices["normalPrice"] = list_price
            discount_percent = round((1 - sale_price / list_price) * 100)
        if card_price:
            prices["cmrPrice"] = card_price

        url = f"https://www.hites.com{href_match.group(1)}" if href_match else ""

        yield {
            "sku_id": pid,
            "product_id": pid,
            "display_name": html.unescape(alt_match.group(1)) if alt_match else "",
            "brand": "",
            "seller_id": "",
            "seller_name": "Hites",
            "url": url,
            "media_url": img_match.group(1) if img_match else None,
            "prices": prices,
            "discount_percent": discount_percent,
        }
