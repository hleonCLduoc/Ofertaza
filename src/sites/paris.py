import json
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "paris"

CATEGORIES = [
    "notebook",
    "celular",
    "smartphone",
    "computador",
    "cama europea 1.5 plazas",
    "cama europea 2 plazas",
    "cama king size",
]

BASE_URL = "https://www.paris.cl/search/"

# Paris (Next.js App Router) no trae un __NEXT_DATA__ simple: los datos viajan
# troceados dentro de llamadas self.__next_f.push([id, "texto-JS-escapado"]).
# Hay que decodificar cada trozo como si fuera un string JS y pegarlos en orden
# para poder encontrar el bloque productData con los productos.
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[(\d+),"((?:\\.|[^"\\])*)"\]\)')

logger = logging.getLogger("sites.paris")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _decode_rsc_payload(html):
    decoded_parts = []
    for _, raw in PUSH_RE.findall(html):
        try:
            decoded_parts.append(json.loads('"' + raw + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(decoded_parts)


def _extract_balanced_json(text, start_idx):
    """text[start_idx] debe ser '{'. Devuelve el substring balanceado hasta su '}' de cierre,
    respetando strings JSON (comillas escapadas, etc.)."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]
    return None


def fetch_page(term, page):
    resp = session.get(
        BASE_URL, params={"q": term, "commune": "13114", "page": page}, timeout=20
    )
    resp.raise_for_status()
    decoded = _decode_rsc_payload(resp.text)

    anchor = '"productData":{'
    idx = decoded.find(anchor)
    if idx == -1:
        logger.warning("No se encontró productData para %r página %s", term, page)
        return None

    start = idx + len('"productData":')
    json_str = _extract_balanced_json(decoded, start)
    if json_str is None:
        logger.warning("No se pudo balancear el JSON de productData para %r página %s", term, page)
        return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("productData inválido para %r página %s", term, page)
        return None


def get_pagination(page_data):
    return page_data.get("total", 0), page_data.get("limit", 30) or 30


def _cents(price_block):
    if not price_block or not isinstance(price_block, dict):
        return None
    value = price_block.get("value")
    if not isinstance(value, dict):
        return None
    return value.get("centAmount")


def iter_products(page_data):
    for product in page_data.get("products", []):
        master = product.get("masterVariant") or {}
        sku_id = master.get("sku") or product.get("id")
        if not sku_id:
            continue

        prices_block = master.get("prices") or {}
        prices = {}
        regular = _cents(prices_block.get("regular"))
        offer = _cents(prices_block.get("offer"))
        payment_method = _cents(prices_block.get("paymentMethod"))
        if regular is not None:
            prices["normalPrice"] = regular
        if offer is not None:
            prices["internetPrice"] = offer
        elif regular is not None:
            prices["internetPrice"] = regular
        if payment_method is not None:
            prices["cmrPrice"] = payment_method

        discounts = [
            prices_block.get("offer", {}).get("discountOnRegular"),
            prices_block.get("paymentMethod", {}).get("discountOnRegular"),
        ]
        discounts = [d for d in discounts if isinstance(d, (int, float))]
        discount_percent = round(max(discounts) * 100) if discounts else None

        sellers = product.get("sellers")
        seller_name = sellers[0] if isinstance(sellers, list) and sellers else "Paris"

        slug = product.get("slug", "")
        url = f"https://www.paris.cl/{slug}.html" if slug else ""

        images = master.get("images") or []
        media_url = images[0].get("url") if images and isinstance(images[0], dict) else None

        yield {
            "sku_id": str(sku_id),
            "product_id": str(product.get("id", "")),
            "display_name": product.get("name", ""),
            "brand": product.get("brand", "") if isinstance(product.get("brand"), str) else "",
            "seller_id": "",
            "seller_name": seller_name,
            "url": url,
            "media_url": media_url,
            "prices": prices,
            "discount_percent": discount_percent,
        }
