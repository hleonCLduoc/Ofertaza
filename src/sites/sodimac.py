import json
import logging
import re

import requests

from config import USER_AGENT

SITE_ID = "sodimac"

# El buscador de texto libre de Sodimac es muy poco confiable (la mayoría
# de los términos no resuelven a una categoría real). En su lugar, se usan
# rutas de categoría reales sacadas directo de la navegación del sitio.
CATEGORY_PATHS = {
    "taladro": "cat14080023/Taladros",
    "pintura interior": "CATG10841/Pintura-para-interior",
    "sierras": "CATG10893/Serruchos-y-sierras",
    "cemento": "CATG10923/Cemento",
    "cortadora de pasto": "cat14080024/Cortadoras-de-pasto",
    "parrillas": "CATG10505/Parrillas-Portatiles",
    "zapatos de seguridad": "CATG10787/Zapatos-de-Seguridad",
    "ampolletas": "CATG10093/Ampolletas-y-tubos",
    "riego de jardin": "CATG10519/Riego-de-Jardin",
    "herramientas electricas": "cat18320014/Herramientas-electricas-e-inalambricas",
    "extensiones electricas": "CATG10801/Alargadores-y-Extensiones-Electricas",
    "cafeteras electricas": "cat3045/Cafeteras-electricas",
    "parrillas electricas": "cat3174/Parrillas-Electricas",
    "colchones": "cat2020/Colchones",
    "refrigeradores": "cat3205/Refrigeradores",
    "lavadoras": "cat4060/Lavadoras",
    "aire acondicionado": "cat2019/Aire-acondicionado",
    "ventiladores": "cat3254/Ventiladores",
    "calefont y termos": "cat2013/Calefont-y-Termos",
    "estufas": "CATG10178/Estufas",
    "closet": "cat3063/Closet",
    "cerraduras digitales": "CATG11151/Cerraduras-Digitales",
    "hidrolavadoras": "cat9560006/Hidrolavadoras",
    "piscinas estructurales": "cat15180001/Piscinas-Estructurales",
    "bombas de piscina": "CATG10511/Bombas-y-Equipos-de-Piscinas",
    "sillas de escritorio": "cat9130008/Sillas-de-Escritorio",
    "sillas gamer": "CATG19011/Sillas-gamer",
    "sillas de comedor": "cat3229/Sillas-de-Comedor",
    "parrilla a gas": "cat2450139/Parrilla-a-gas",
}

CATEGORIES = list(CATEGORY_PATHS.keys())

BASE_URL = "https://www.sodimac.cl/sodimac-cl/lista"

NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

logger = logging.getLogger("sites.sodimac")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch_page(term, page):
    path = CATEGORY_PATHS.get(term)
    if not path:
        logger.warning("Categoría desconocida para sodimac: %r", term)
        return None

    resp = session.get(f"{BASE_URL}/{path}", params={"page": page}, timeout=20)
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
